from __future__ import annotations

from pathlib import Path

import yaml

from aspen_automation import load_spec
from aspen_automation.process_spec_coherence import (
    analyze_process_spec_coherence,
    apply_process_spec_improvements,
    build_codex_improvement_markdown,
    build_codex_spec_markdown,
    suggest_process_spec_improvements,
    write_process_spec_file,
)
from aspen_automation.process_library import load_process_spec, validate_process_spec_file
from aspen_automation.serialization import spec_to_plain_dict


ROOT = Path(__file__).resolve().parents[1]
METHANOL_PROCESS_DIR = ROOT / "process_library" / "methanol"
METHANOL_TEMPLATE_PATH = ROOT / "templates" / "methanol_plant_atr.yaml"


def test_analyze_process_spec_coherence_warns_on_sep_high_purity_case() -> None:
    spec = load_spec(str(METHANOL_TEMPLATE_PATH))

    report = analyze_process_spec_coherence(spec)

    assert report["passed"] is True
    warnings = [issue for issue in report["issues"] if issue["severity"] == "warning"]
    assert any("High-purity target" in issue["message"] for issue in warnings)
    assert any("Property method" in issue["message"] for issue in warnings)


def test_build_codex_spec_markdown_includes_blocking_gate_message() -> None:
    spec_path = METHANOL_TEMPLATE_PATH
    spec = load_spec(str(spec_path))
    spec_dict = spec_to_plain_dict(spec)
    split_block = next(block for block in spec_dict["blocks"] if block["name"] == "SPLIT")
    split_block["split_fractions"][1]["fraction"] = 0.10
    validation_report = validate_process_spec_file(spec_path)
    coherence_report = analyze_process_spec_coherence(spec_dict)

    markdown = build_codex_spec_markdown(
        "methanol",
        spec_path,
        validation_report,
        coherence_report,
        spec=spec_dict,
    )

    assert "Codex Session: YAML Coherence `methanol`" in markdown
    assert "Structural validation: passed" in markdown
    assert "Why this did not pass the coherence test:" in markdown
    assert "Execution gate: blocked" in markdown


def test_suggest_process_spec_improvements_returns_expected_items() -> None:
    spec = load_spec(str(METHANOL_TEMPLATE_PATH))
    coherence_report = analyze_process_spec_coherence(spec)

    suggestions = suggest_process_spec_improvements(spec, coherence_report)

    suggestion_ids = {suggestion["id"] for suggestion in suggestions}
    assert "upgrade_final_separator_to_radfrac" in suggestion_ids
    assert "switch_property_method_to_nrtl" in suggestion_ids
    assert "add_explicit_databanks" in suggestion_ids
    radfrac = next(suggestion for suggestion in suggestions if suggestion["id"] == "upgrade_final_separator_to_radfrac")
    assert radfrac["auto_applicable"] is False


def test_apply_process_spec_improvements_keeps_buildable_separator_baseline() -> None:
    spec = load_spec(str(METHANOL_TEMPLATE_PATH))
    coherence_report = analyze_process_spec_coherence(spec)
    suggestions = suggest_process_spec_improvements(spec, coherence_report)

    updated_spec, applied = apply_process_spec_improvements(
        spec,
        suggestions,
        selected_ids=[
            "switch_property_method_to_nrtl",
            "add_explicit_databanks",
        ],
    )
    updated_report = analyze_process_spec_coherence(updated_spec)

    assert {suggestion["id"] for suggestion in applied} == {
        "switch_property_method_to_nrtl",
        "add_explicit_databanks",
    }
    assert updated_spec["properties"]["method"] == "NRTL"
    assert updated_spec["properties"]["databanks"]
    dist_block = next(block for block in updated_spec["blocks"] if block["name"] == "B-DIST")
    assert dist_block["type"] == "SEP"
    assert updated_report["passed"] is True


def test_nrtl_high_purity_methanol_water_warns_without_binary_parameter_source() -> None:
    spec = load_spec(str(METHANOL_TEMPLATE_PATH))
    spec_dict = spec_to_plain_dict(spec)
    spec_dict["properties"]["method"] = "NRTL"
    spec_dict["properties"]["databanks"] = [
        "APV140 PURE32",
        "APV140 AQUEOUS",
        "APV140 SOLIDS",
        "APV140 INORGANIC",
    ]

    report = analyze_process_spec_coherence(spec_dict)
    suggestions = suggest_process_spec_improvements(spec_dict, report)

    warnings = [issue for issue in report["issues"] if issue["severity"] == "warning"]
    assert any(issue["location"] == "properties.binary_parameters" for issue in warnings)
    assert "add_nrtl_methanol_water_binary_parameter_source" in {item["id"] for item in suggestions}


def test_build_codex_improvement_markdown_describes_notebook_prompt() -> None:
    spec = load_spec(str(METHANOL_TEMPLATE_PATH))
    coherence_report = analyze_process_spec_coherence(spec)
    suggestions = suggest_process_spec_improvements(spec, coherence_report)

    markdown = build_codex_improvement_markdown("methanol", suggestions)

    assert "Suggested YAML Improvements: `methanol`" in markdown
    assert "Automatic improvements available:" in markdown
    assert "Notebook prompt:" in markdown


def test_write_process_spec_file_creates_backup_and_writes_yaml(tmp_path: Path) -> None:
    source_path = tmp_path / "process.yaml"
    source_path.write_text("metadata:\n  title: test\n", encoding="utf-8")

    backup_path = write_process_spec_file(
        source_path,
        {
            "metadata": {
                "title": "Updated",
                "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"},
            },
            "components": [{"id": "A", "name": "A"}],
            "properties": {"method": "NRTL"},
            "flowsheet": [{"block": "B1", "inputs": ["S1"], "outputs": ["S2"]}],
            "streams": [
                {"name": "S1", "temperature": 25.0, "pressure": 1.0, "mass_flow": 1.0, "composition": {"A": 1.0}},
                {"name": "S2", "temperature": 25.0, "pressure": 1.0, "mass_flow": 1.0, "composition": {"A": 1.0}},
            ],
            "blocks": [{"name": "B1", "type": "MIXER"}],
        },
    )

    assert backup_path.is_file()
    assert "title: Updated" in source_path.read_text(encoding="utf-8")


def test_spec_to_plain_dict_converts_nested_reaction_enums() -> None:
    spec = load_spec(str(METHANOL_TEMPLATE_PATH))

    plain_spec = spec_to_plain_dict(spec)

    reaction_type = plain_spec["chemistry"][0]["reactions"][0]["parameters"]["reaction_type"]
    assert reaction_type == "EQUIL"
    assert isinstance(reaction_type, str)


def test_live_process_library_methanol_spec_passes_coherence_with_manual_review_item() -> None:
    spec = load_process_spec(METHANOL_PROCESS_DIR)

    coherence_report = analyze_process_spec_coherence(spec)
    suggestions = suggest_process_spec_improvements(spec, coherence_report)

    syn_block = next(block for block in spec["blocks"] if block["name"] == "B-SYN")
    dist_block = next(block for block in spec["blocks"] if block["name"] == "B-DIST")
    assert syn_block["type"] == "RPLUG"
    assert dist_block["type"] == "RADFRAC"
    assert coherence_report["passed"] is True
    assert all(
        "coarse screening model for final purification" not in issue["message"]
        for issue in coherence_report["issues"]
    )
    assert {suggestion["id"] for suggestion in suggestions} == set()


def test_write_process_spec_file_handles_methanol_improvements_with_nested_enums(tmp_path: Path) -> None:
    spec = load_spec(str(METHANOL_TEMPLATE_PATH))
    coherence_report = analyze_process_spec_coherence(spec)
    suggestions = suggest_process_spec_improvements(spec, coherence_report)
    updated_spec, applied = apply_process_spec_improvements(
        spec,
        suggestions,
        selected_ids=[
            "switch_property_method_to_nrtl",
            "add_explicit_databanks",
        ],
    )

    source_path = tmp_path / "process.yaml"
    source_path.write_text(METHANOL_TEMPLATE_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    backup_path = write_process_spec_file(source_path, updated_spec)
    written_spec = yaml.safe_load(source_path.read_text(encoding="utf-8"))

    assert backup_path.is_file()
    assert {suggestion["id"] for suggestion in applied} == {
        "switch_property_method_to_nrtl",
        "add_explicit_databanks",
    }
    assert written_spec["properties"]["method"] == "NRTL"
    assert written_spec["properties"]["databanks"] == [
        "APV140 PURE32",
        "APV140 AQUEOUS",
        "APV140 SOLIDS",
        "APV140 INORGANIC",
    ]
    dist_block = next(block for block in written_spec["blocks"] if block["name"] == "B-DIST")
    assert dist_block["type"] == "SEP"
    reaction_type = written_spec["chemistry"][0]["reactions"][0]["parameters"]["reaction_type"]
    assert reaction_type == "EQUIL"
