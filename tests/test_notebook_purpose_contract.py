from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import yaml

from aspen_automation import generate_inp, load_spec
from aspen_automation.exceptions import BuildError
from aspen_automation.inp_generator import validate_inp
from aspen_automation.process_library import (
    load_process_spec,
    run_process,
    validate_process_spec_file,
)
from aspen_automation.process_results_analysis import (
    build_codex_results_markdown,
    load_result_artifact_tables,
)
from aspen_automation.process_spec_coherence import analyze_process_spec_coherence


ROOT = Path(__file__).resolve().parents[1]
METHANOL_PROCESS_DIR = ROOT / "process_library" / "methanol"
METHANOL_PROCESS_YAML = METHANOL_PROCESS_DIR / "process.yaml"
NOTEBOOK_PATH = ROOT / "notebooks" / "process_library_runner.ipynb"
METHANOL_NOTEBOOK_PATH = ROOT / "notebooks" / "methanol_example_runner.ipynb"


def _copy_methanol_process(target_process_dir: Path) -> Path:
    target_process_dir.mkdir(parents=True, exist_ok=True)
    target_yaml = target_process_dir / "process.yaml"
    shutil.copy2(METHANOL_PROCESS_YAML, target_yaml)
    return target_yaml


def _fake_extracted_results(*, readable: bool = True) -> dict:
    if not readable:
        return {
            "streams": pd.DataFrame([{"stream_name": "MEOH-PRO", "temperature": None, "mass_flow": None}]),
            "blocks": pd.DataFrame([{"block_name": "B-DIST", "block_type": "SEP", "duty_kw": None}]),
            "material_balance": pd.DataFrame(),
            "energy_balance": pd.DataFrame(),
            "kpis": {
                "production_rate_tpd": None,
                "purity_fraction": None,
                "convergence_status": "unknown",
            },
            "diagnostics": {"convergence_status": "unknown", "per_error": None},
        }

    return {
        "streams": pd.DataFrame(
            [
                {
                    "stream_name": "NG-FEED",
                    "temperature": 40.0,
                    "pressure": 30.0,
                    "mass_flow": 220000.0,
                    "mole_flow": 1000.0,
                    "CH3OH_mass_frac": 0.0,
                    "CH3OH_mole_frac": 0.0,
                },
                {
                    "stream_name": "MEOH-PRO",
                    "temperature": 40.0,
                    "pressure": 1.5,
                    "mass_flow": 416666.7,
                    "mole_flow": 13000.0,
                    "CH3OH_mass_frac": 0.9986,
                    "CH3OH_mole_frac": 0.9986,
                },
                {
                    "stream_name": "VENT-GAS",
                    "temperature": 30.0,
                    "pressure": 1.8,
                    "mass_flow": 75000.0,
                    "mole_flow": 4000.0,
                    "CH3OH_mass_frac": 0.30,
                    "CH3OH_mole_frac": 0.18,
                },
                {
                    "stream_name": "VENT-TOT",
                    "temperature": 54.0,
                    "pressure": 1.5,
                    "mass_flow": 64060.0,
                    "mole_flow": 1986.0,
                    "CH3OH_mass_frac": 0.38,
                    "CH3OH_mole_frac": 0.384,
                },
            ]
        ),
        "blocks": pd.DataFrame(
            [
                {"block_name": "B-ATR", "block_type": "RGIBBS", "duty": 2500.0, "duty_kw": 2500.0, "duty_mw": 2.5},
                {"block_name": "B-DIST", "block_type": "SEP", "duty": -1000.0, "duty_kw": -1000.0, "duty_mw": -1.0},
            ]
        ),
        "material_balance": pd.DataFrame(
            [{"component": "CH3OH", "component_id": "CH3OH", "input_kmol_hr": 10.0, "output_kmol_hr": 9.99, "closure_pct": -0.1}]
        ),
        "energy_balance": pd.DataFrame(
            [
                {"block_name": "B-ATR", "duty": 2500.0, "duty_kw": 2500.0, "duty_mw": 2.5},
                {"block_name": "TOTAL", "duty": 1500.0, "duty_kw": 1500.0, "duty_mw": 1.5},
            ]
        ),
        "kpis": {
            "production_rate_tpd": 10000.0,
            "purity_fraction": 0.9986,
            "energy_consumption_mw": 3.5,
            "yield_fraction": 0.85,
            "convergence_status": "converged",
        },
        "diagnostics": {"convergence_status": "converged", "per_error": 0},
        "metadata": {"stream_count": 3, "block_count": 2, "component_count": 8},
    }


def _fake_session_result(*, aspen: object | None, status: str = "converged") -> SimpleNamespace:
    return SimpleNamespace(
        build_mode="auto",
        build_mechanism_used="com_block_builder",
        build_fallback_attempted=False,
        diagnostics={
            "build_valid": aspen is not None,
            "flowsheet_verification": {
                "build_valid": aspen is not None,
                "stream_count": 17 if aspen is not None else 0,
                "block_count": 10 if aspen is not None else 0,
                "stream_samples": ["NG-FEED", "STEAM", "O2-FEED"] if aspen is not None else [],
                "block_samples": ["MIX-FEED", "B-ATR"] if aspen is not None else [],
            },
            "convergence_status": status,
            "per_error": 0 if status == "converged" else 1,
        },
        convergence_status=status,
        simulation_time_seconds=12.5,
        aspen=aspen,
    )


def _cell_source(cell: dict) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(source)
    return str(source)


def test_codex_authored_yaml_contract_validates() -> None:
    spec = load_process_spec(METHANOL_PROCESS_DIR)
    required_sections = {"metadata", "components", "properties", "flowsheet", "streams", "blocks"}

    assert required_sections.issubset(spec)
    validation_report = validate_process_spec_file(METHANOL_PROCESS_YAML)
    assert validation_report["valid"], validation_report["errors"]

    component_ids = {component["id"] for component in spec["components"]}
    stream_names = {stream["name"] for stream in spec["streams"]}
    block_names = {block["name"] for block in spec["blocks"]}

    for stream in spec["streams"]:
        assert set(stream["composition"]).issubset(component_ids)
    for connection in spec["flowsheet"]:
        assert connection["block"] in block_names
        assert set(connection["inputs"]).issubset(stream_names)
        assert set(connection["outputs"]).issubset(stream_names)

    coherence_report = analyze_process_spec_coherence(spec)
    blocking_errors = [issue for issue in coherence_report["issues"] if issue["severity"] == "error"]
    assert coherence_report["passed"] is True
    assert blocking_errors == []


def test_codex_authored_yaml_generates_valid_inp() -> None:
    spec = load_spec(str(METHANOL_PROCESS_YAML))
    inp = generate_inp(spec)

    report = validate_inp(inp)
    assert report["valid"], report["errors"]
    assert "TITLE 'Methanol Plant 10k TPD'" in inp
    assert "IN-UNITS MET PRESSURE=BAR TEMPERATURE=C FLOW='KG/HR'" in inp
    assert "DATABANKS" in inp
    assert "APV140 PURE32" in inp
    assert "COMPONENTS" in inp
    assert "CH4 METHANE" in inp
    assert "PROPERTIES NRTL" in inp
    assert "FLOWSHEET" in inp
    assert "STREAM NG-FEED" in inp
    assert "BLOCK MIX-FEED MIXER" in inp
    assert "BLOCK B-SYN RPLUG" in inp
    assert "REACTIONS RXN-SET1 POWERLAW" in inp
    assert "REAC-DATA 1 KINETIC" in inp
    assert "CBASIS=MOLARITY" in inp
    assert "RBASIS=" not in inp
    assert "RATE-CON 1" in inp
    stoic_lines = [line for line in inp.splitlines() if line.strip().startswith("STOIC")]
    assert not any("CH4" in line for line in stoic_lines)


def test_process_run_mocked_end_to_end_outputs_user_tables(tmp_path: Path) -> None:
    process_dir = tmp_path / "process_library" / "methanol"
    _copy_methanol_process(process_dir)
    runs_root = tmp_path / "process_runs"

    fake_aspen = MagicMock(name="aspen")
    fake_aspen.SaveAs.side_effect = lambda path: Path(path).write_text("mock apw", encoding="utf-8")

    with (
        patch(
            "aspen_automation.process_library.run_simulation_session",
            return_value=_fake_session_result(aspen=fake_aspen),
        ) as mock_session,
        patch("aspen_automation.process_library.extract_results", return_value=_fake_extracted_results()),
    ):
        result = run_process(process_dir, runs_root, visible=False, build_mode="auto")

    assert result.succeeded
    assert result.status == "succeeded"
    assert result.layout is not None
    assert result.report_dir is not None
    assert result.layout.generated_inp_path.is_file()
    assert result.layout.output_apw_path.is_file()
    fake_aspen.SaveAs.assert_called_once_with(str(result.layout.output_apw_path))
    mock_session.assert_called_once()

    expected_result_files = {
        "streams.csv",
        "blocks.csv",
        "material_balance.csv",
        "energy_balance.csv",
        "kpis.json",
        "diagnostics.json",
        "acceptance.json",
        "build_diagnostics.json",
        "simulation_diagnostics.json",
    }
    assert expected_result_files.issubset({path.name for path in result.layout.results_dir.iterdir()})
    assert (result.report_dir / "run_summary.html").is_file()
    assert "methanol_generated.inp" in result.generated_files
    assert "methanol_output.apw" in result.generated_files


def test_result_tables_are_analysis_ready(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    fake_results = _fake_extracted_results()

    for key in ["streams", "blocks", "material_balance", "energy_balance"]:
        fake_results[key].to_csv(results_dir / f"{key}.csv", index=False)

    result = SimpleNamespace(report_dir=None, layout=SimpleNamespace(results_dir=results_dir))
    artifact_paths, tables = load_result_artifact_tables(result)

    assert set(artifact_paths) == {"streams", "blocks", "material_balance", "energy_balance"}
    assert {"stream_name", "temperature", "mass_flow", "CH3OH_mass_frac"}.issubset(tables["streams"].columns)
    assert {"block_name", "block_type", "duty_kw", "duty_mw"}.issubset(tables["blocks"].columns)
    assert {"component", "input_kmol_hr", "output_kmol_hr", "closure_pct"}.issubset(tables["material_balance"].columns)
    assert {"block_name", "duty_kw", "duty_mw"}.issubset(tables["energy_balance"].columns)

    markdown = build_codex_results_markdown(
        "methanol",
        artifact_paths,
        tables,
        acceptance={"passed": True},
    )

    assert "Codex Session Analysis: `methanol`" in markdown
    assert "MEOH-PRO" in markdown
    assert "Largest absolute block duties" in markdown
    assert "Acceptance status from `acceptance.json`: True." in markdown


def test_execution_gates_block_invalid_and_incoherent_specs(tmp_path: Path) -> None:
    invalid_dir = tmp_path / "process_library" / "invalid"
    invalid_dir.mkdir(parents=True)
    invalid_yaml = yaml.safe_load(METHANOL_PROCESS_YAML.read_text(encoding="utf-8"))
    invalid_yaml.pop("components")
    (invalid_dir / "process.yaml").write_text(yaml.safe_dump(invalid_yaml, sort_keys=False), encoding="utf-8")

    with patch("aspen_automation.process_library.run_simulation_session") as mock_session:
        invalid_result = run_process(invalid_dir, tmp_path / "process_runs")

    assert invalid_result.status == "validation_failed"
    mock_session.assert_not_called()

    incoherent_dir = tmp_path / "process_library" / "incoherent"
    _copy_methanol_process(incoherent_dir)
    coherence_failure = {
        "passed": False,
        "issues": [
            {
                "severity": "error",
                "location": "blocks[SPLIT].split_fractions",
                "message": "Split fractions do not sum to 1.0.",
                "suggestion": "Normalize outlet fractions.",
            }
        ],
    }

    with (
        patch("aspen_automation.process_library.analyze_process_spec_coherence", return_value=coherence_failure),
        patch("aspen_automation.process_library.run_simulation_session") as mock_session,
    ):
        incoherent_result = run_process(incoherent_dir, tmp_path / "process_runs")

    assert incoherent_result.status == "coherence_failed"
    assert incoherent_result.layout is not None
    assert (incoherent_result.layout.results_dir / "coherence_report.json").is_file()
    mock_session.assert_not_called()


def test_execution_gates_report_runtime_failure_statuses(tmp_path: Path) -> None:
    build_dir = tmp_path / "process_library" / "build_failure"
    _copy_methanol_process(build_dir)
    build_error = BuildError(
        "COM block builder failed",
        build_mode="auto",
        mechanism_tried="com_block_builder",
        diagnostics={
            "build_valid": False,
            "flowsheet_verification": {"build_valid": False, "stream_count": 0, "block_count": 0},
        },
    )

    with patch("aspen_automation.process_library.run_simulation_session", side_effect=build_error):
        build_result = run_process(build_dir, tmp_path / "process_runs")

    assert build_result.status == "build_failed"
    assert build_result.layout is not None
    assert (build_result.layout.results_dir / "build_diagnostics.json").is_file()
    assert (build_result.layout.results_dir / "simulation_diagnostics.json").is_file()

    connection_dir = tmp_path / "process_library" / "connection_failure"
    _copy_methanol_process(connection_dir)
    connection_result_payload = _fake_session_result(aspen=None, status="failed")
    connection_result_payload.diagnostics.update(
        {
            "error": "Aspen Plus is not running.",
            "connection_error_type": "AspenConnectionError",
            "aspen_preflight": {"connection_verified": False, "preflight_status": "init_failed"},
        }
    )

    with patch("aspen_automation.process_library.run_simulation_session", return_value=connection_result_payload):
        connection_result = run_process(connection_dir, tmp_path / "process_runs")

    assert connection_result.status == "connection_failed"
    assert connection_result.layout is not None
    assert (connection_result.layout.results_dir / "build_diagnostics.json").is_file()
    assert (connection_result.layout.results_dir / "simulation_diagnostics.json").is_file()

    simulation_dir = tmp_path / "process_library" / "simulation_failure"
    _copy_methanol_process(simulation_dir)
    fake_aspen = MagicMock(name="aspen")

    with patch(
        "aspen_automation.process_library.run_simulation_session",
        return_value=_fake_session_result(aspen=fake_aspen, status="failed"),
    ):
        simulation_result = run_process(simulation_dir, tmp_path / "process_runs")

    assert simulation_result.status == "simulation_failed"
    assert simulation_result.layout is not None
    assert (simulation_result.layout.results_dir / "simulation_diagnostics.json").is_file()

    unreadable_dir = tmp_path / "process_library" / "unreadable_results"
    _copy_methanol_process(unreadable_dir)
    fake_aspen = MagicMock(name="aspen")
    fake_aspen.SaveAs.side_effect = lambda path: Path(path).write_text("mock apw", encoding="utf-8")

    with (
        patch(
            "aspen_automation.process_library.run_simulation_session",
            return_value=_fake_session_result(aspen=fake_aspen, status="converged"),
        ),
        patch("aspen_automation.process_library.extract_results", return_value=_fake_extracted_results(readable=False)),
    ):
        unreadable_result = run_process(unreadable_dir, tmp_path / "process_runs")

    assert unreadable_result.status == "results_unreadable"
    assert unreadable_result.layout is not None
    assert (unreadable_result.layout.results_dir / "yaml_update_suggestions.json").is_file()


def test_notebook_static_contract() -> None:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    joined_sources = "\n".join(_cell_source(cell) for cell in notebook["cells"])

    ordered_markers = [
        "Process Library Runner: Process-Agnostic Batch-First Aspen Workflow",
        "Environment setup and imports",
        "Aspen Plus pre-flight check",
        "Process evidence intake for Codex-authored YAML",
        "Process library path configuration",
        "Discovery of all available process folders",
        "YAML coherence analysis per discovered process",
        "Suggested YAML improvements per discovered process",
        "Gate 1: Aspen batch translator",
        "Gate 2: BKP COM load, extraction, and reports",
        "Gate 2 diagnostics and evidence bundle",
        "Codex session analysis per discovered process",
        "Output summary and validation",
    ]
    marker_positions = [joined_sources.index(marker) for marker in ordered_markers]
    assert marker_positions == sorted(marker_positions)

    assert "build_process_intake_artifacts" in joined_sources
    assert "PROCESS_NAME" in joined_sources
    assert "USER_PROCESS_BRIEF" in joined_sources
    assert "SOURCE_PDFS" in joined_sources
    assert "SOURCE_URLS" in joined_sources
    assert "WEB_SEARCH_QUERIES" in joined_sources
    assert "REFERENCE_NOTES" in joined_sources
    assert "source_manifest.json" in joined_sources
    assert "process_research_brief.md" in joined_sources
    assert "codex_process_yaml_prompt.md" in joined_sources
    assert joined_sources.index("check_aspen_running") < joined_sources.index("run_aspen_batch(")
    assert joined_sources.index("run_aspen_batch(") < joined_sources.index("run_process_batch_first(")
    assert "run_process(" not in joined_sources
    assert "generate_inp" in joined_sources
    assert "load_spec" in joined_sources
    assert "run_process_batch_first" in joined_sources
    assert "ENFORCE_ACCEPTANCE_TARGETS = False" in joined_sources
    assert "enforce_acceptance_targets=ENFORCE_ACCEPTANCE_TARGETS" in joined_sources
    assert "def batch_history_path" in joined_sources
    assert "batch_result.history_path" not in joined_sources
    assert "context_probe.json" in joined_sources
    assert "build_diagnostics.json" in joined_sources
    assert "simulation_diagnostics.json" in joined_sources
    assert "live_aspen_summary.json" in joined_sources
    assert "validate_process_spec_file" in joined_sources
    assert "analyze_process_spec_coherence" in joined_sources
    assert "build_codex_spec_markdown(process.name, process.spec_path, validation_report, coherence_report)" in joined_sources
    assert "suggest_process_spec_improvements" in joined_sources
    assert "write_process_spec_file" in joined_sources
    assert "load_result_artifact_tables" in joined_sources
    assert "build_codex_results_markdown" in joined_sources
    assert "B-SYN selectivity diagnostics" not in joined_sources
    assert "PURGE_SWEEP_FRACTIONS" not in joined_sources
    assert "ATR_TUNING_FACTORS" not in joined_sources
    assert "run_methanol_tuning_campaign" not in joined_sources
    assert "MEOH-PRO" not in joined_sources
    analysis_cell = next(
        _cell_source(cell)
        for cell in notebook["cells"]
        if cell.get("id") == "codex-csv-analysis"
    )
    assert analysis_cell.index("if not result.succeeded:") < analysis_cell.index("load_result_artifact_tables(result)")


def test_methanol_example_notebook_contains_methanol_specific_workflow() -> None:
    notebook = json.loads(METHANOL_NOTEBOOK_PATH.read_text(encoding="utf-8"))
    joined_sources = "\n".join(_cell_source(cell) for cell in notebook["cells"])

    assert "Methanol Example Runner: Kinetic Batch-First Aspen Workflow" in joined_sources
    assert 'ONLY_PROCESSES: set[str] | None = {"methanol"}' in joined_sources
    assert "B-SYN selectivity diagnostics" in joined_sources
    assert "recycle composition diagnostics" in joined_sources
    assert "PURGE_SWEEP_FRACTIONS" in joined_sources
    assert "ATR_TUNING_FACTORS" in joined_sources
    assert "run_methanol_tuning_campaign" in joined_sources
    assert "tuning_campaign_summary.csv" in joined_sources
    assert "tuning_campaign_summary.json" in joined_sources
    assert "best_process.yaml" in joined_sources
