from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from aspen_automation.capsule_context import collect_capsule_context


def test_collect_capsule_context_records_process_com_package_and_optional_diagnostics(tmp_path: Path) -> None:
    engine_path = tmp_path / "aspen.exe"
    engine_path.write_text("engine", encoding="utf-8")
    fake_aspen = SimpleNamespace(
        Version="40.0",
        Name="Aspen Plus",
        FullName="Aspen Plus V14",
        Path=str(tmp_path),
        Application=SimpleNamespace(Version="40.0", Name="Aspen Plus App"),
    )

    with patch(
        "aspen_automation.capsule_context._get_process_ancestry",
        return_value={"status": "collected", "processes": [{"Name": "python.exe"}]},
    ), patch(
        "aspen_automation.capsule_context._detect_package_markers",
        return_value={
            "status": "collected",
            "suspected_appanywhere_virtualization": True,
            "matching_environment": {"CLOUDPAGING_TEST": "1"},
            "matching_process_lines": ["Cloudpaging.exe"],
        },
    ), patch(
        "aspen_automation.capsule_context._probe_localization_assembly",
        return_value={
            "status": "visible",
            "assembly": "AspenTech.AspenPlus.Localization",
            "visible": True,
        },
    ), patch(
        "aspen_automation.capsule_context._probe_optional_diagnostic_tools",
        return_value={
            "fusion": {"status": "skipped"},
            "procmon": {"status": "skipped"},
        },
    ):
        context = collect_capsule_context(aspen=fake_aspen, engine_path=engine_path)

    assert context["process_ancestry"]["status"] == "collected"
    assert context["resolved_aspen_engine"]["path"] == str(engine_path)
    assert context["resolved_aspen_engine"]["exists"] is True
    assert context["com_identity"]["document"]["Version"] == "40.0"
    assert context["package_markers"]["suspected_appanywhere_virtualization"] is True
    assert context["localization_assembly"]["visible"] is True
    assert context["optional_diagnostics"]["fusion"]["status"] == "skipped"
    assert context["optional_diagnostics"]["procmon"]["status"] == "skipped"
