from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
from typing import Any

import pytest

from aspen_automation.process_library import run_process
from aspen_automation.process_results_analysis import (
    build_codex_results_markdown,
    load_result_artifact_tables,
)
from aspen_automation.session import check_aspen_running


ROOT = Path(__file__).resolve().parents[2]
METHANOL_PROCESS_DIR = ROOT / "process_library" / "methanol"
LIVE_RESULTS_ROOT = ROOT / "test_results" / "live_aspen_methanol"
APPANYWHERE_PROCESS_TOKENS = (
    "appanywhere",
    "appsanywhere",
    "cloudpaging",
    "software2",
    "s2apps",
    "s2launcher",
)
APPANYWHERE_ENV_TOKENS = (
    "APPANYWHERE",
    "APPSANYWHERE",
    "CLOUDPAGING",
    "SOFTWARE2",
    "S2APPS",
)

try:
    import win32com.client  # noqa: F401
except Exception as exc:  # pragma: no cover - environment-specific
    PYWIN32_IMPORT_ERROR: Exception | None = exc
else:  # pragma: no cover - environment-specific
    PYWIN32_IMPORT_ERROR = None


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _detect_virtualized_aspen_context() -> dict[str, Any]:
    env_matches = sorted(
        key
        for key in os.environ
        if any(token in key.upper() for token in APPANYWHERE_ENV_TOKENS)
    )
    process_matches: list[str] = []
    tasklist_error = None
    tasklist_command: list[str] = []
    try:
        tasklist_command = ["tasklist", "/FO", "CSV", "/NH"]
        completed = subprocess.run(
            tasklist_command,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if completed.returncode != 0:
            tasklist_error = completed.stderr.strip() or completed.stdout.strip()
        for line in completed.stdout.splitlines():
            lower_line = line.lower()
            if any(token in lower_line for token in APPANYWHERE_PROCESS_TOKENS):
                process_matches.append(line)
    except Exception as exc:  # pragma: no cover - host specific
        tasklist_error = str(exc)

    return {
        "suspected_appanywhere_virtualization": bool(env_matches or process_matches),
        "matching_environment_variable_names": env_matches,
        "matching_process_lines": process_matches[:20],
        "tasklist_command": tasklist_command,
        "tasklist_error": tasklist_error,
        "note": (
            "Aspen Plus appears to be running from an AppAnywhere/Cloudpaging-style virtualization layer."
            if env_matches or process_matches
            else "No AppAnywhere/Cloudpaging process or environment marker was detected from pytest."
        ),
    }


def _classify_live_aspen_failure(
    result: Any,
    *,
    build_diagnostics: dict[str, Any],
    simulation_diagnostics: dict[str, Any],
    environment: dict[str, Any],
) -> dict[str, Any]:
    payload_text = json.dumps(
        {
            "status": getattr(result, "status", None),
            "error": getattr(result, "error", None),
            "details": getattr(result, "details", {}),
            "build_diagnostics": build_diagnostics,
            "simulation_diagnostics": simulation_diagnostics,
        },
        default=str,
    ).lower()

    if "aspentech.aspenplus.localization" in payload_text or (
        "presentationframework" in payload_text and "unable to create block" in payload_text
    ):
        return {
            "category": "appanywhere_virtualization_dependency",
            "summary": (
                "Aspen COM connected and the auto COM builder started, but block creation triggered "
                "Aspen's WPF/model-library dependency loading and could not load "
                "AspenTech.AspenPlus.Localization."
            ),
            "recommended_action": (
                "Launch Aspen Plus V14 from AppAnywhere/Porticada, wait until the virtualized package is "
                "fully staged, keep Aspen open, and rerun the live test. If the same error persists, the "
                "AppAnywhere package likely needs the missing AspenTech.AspenPlus.Localization assembly or "
                "a locally installed Aspen Plus runtime for COM automation."
            ),
            "appanywhere_context_detected": bool(environment.get("suspected_appanywhere_virtualization")),
            "virtualization_dependency_signature_detected": True,
        }

    if "isolated_inp_import_worker" in payload_text or "legacy aspen inp import path" in payload_text:
        return {
            "category": "legacy_inp_import_path",
            "summary": "The failure came from the legacy INP import route rather than the robust auto COM builder path.",
            "recommended_action": "Run this live test with the pinned build_mode='auto' path.",
            "appanywhere_context_detected": bool(environment.get("suspected_appanywhere_virtualization")),
            "virtualization_dependency_signature_detected": False,
        }

    if bool(environment.get("suspected_appanywhere_virtualization")) and getattr(result, "status", None) != "succeeded":
        return {
            "category": "appanywhere_virtualization_context",
            "summary": "Aspen failed while AppAnywhere/Cloudpaging virtualization markers were present.",
            "recommended_action": (
                "Confirm Aspen Plus is fully launched and licensed through AppAnywhere before rerunning; "
                "if COM still fails, compare against a non-virtualized Aspen installation."
            ),
            "appanywhere_context_detected": True,
            "virtualization_dependency_signature_detected": False,
        }

    return {
        "category": "unclassified",
        "summary": "No AppAnywhere-specific failure signature was detected.",
        "recommended_action": "Review build_diagnostics.json and simulation_diagnostics.json for the primary Aspen error.",
        "appanywhere_context_detected": bool(environment.get("suspected_appanywhere_virtualization")),
        "virtualization_dependency_signature_detected": False,
    }


def _require_live_aspen_ready() -> None:
    if os.environ.get("ASPEN_PLUS_INTEGRATION") != "1":
        pytest.skip("Set ASPEN_PLUS_INTEGRATION=1 to run the live Aspen Plus process-library test")

    if PYWIN32_IMPORT_ERROR is not None:
        pytest.fail(f"ASPEN_PLUS_INTEGRATION=1 was set, but pywin32 is unavailable: {PYWIN32_IMPORT_ERROR}")

    if not (METHANOL_PROCESS_DIR / "process.yaml").is_file():
        pytest.fail(f"Canonical methanol process YAML was not found: {METHANOL_PROCESS_DIR / 'process.yaml'}")

    if not check_aspen_running():
        pytest.fail(
            "ASPEN_PLUS_INTEGRATION=1 was set, but AspenPlus.exe is not running. "
            "Launch Aspen Plus V14 before running this live test."
        )


def _persist_live_analysis(result: Any) -> tuple[Path | None, Path | None, dict[str, Any]]:
    layout = getattr(result, "layout", None)
    if layout is None:
        return None, None, {}

    artifact_paths, tables = load_result_artifact_tables(result)
    acceptance = _read_json(layout.results_dir / "acceptance.json")
    kpis = _read_json(layout.results_dir / "kpis.json")
    build_diagnostics = _read_json(layout.results_dir / "build_diagnostics.json")
    simulation_diagnostics = _read_json(layout.results_dir / "simulation_diagnostics.json")
    environment = _detect_virtualized_aspen_context()
    failure_classification = _classify_live_aspen_failure(
        result,
        build_diagnostics=build_diagnostics,
        simulation_diagnostics=simulation_diagnostics,
        environment=environment,
    )

    markdown = build_codex_results_markdown(
        result.process_name,
        artifact_paths,
        tables,
        acceptance=acceptance or None,
    )
    analysis_path = layout.run_dir / "live_aspen_analysis.md"
    analysis_path.write_text(markdown + "\n", encoding="utf-8")

    summary = {
        "process_name": result.process_name,
        "status": result.status,
        "succeeded": result.succeeded,
        "error": result.error,
        "process_dir": str(result.process_dir),
        "spec_path": str(result.spec_path) if result.spec_path else None,
        "run_dir": str(layout.run_dir),
        "generated_inp_path": str(layout.generated_inp_path),
        "output_apw_path": str(layout.output_apw_path),
        "results_dir": str(layout.results_dir),
        "report_dir": str(result.report_dir) if result.report_dir else None,
        "analysis_markdown_path": str(analysis_path),
        "artifact_paths": {name: str(path) for name, path in artifact_paths.items()},
        "csv_shapes": {
            name: {"rows": int(len(table)), "columns": [str(column) for column in table.columns]}
            for name, table in tables.items()
        },
        "build": {
            "status": build_diagnostics.get("status"),
            "build_mode": build_diagnostics.get("build_mode"),
            "build_mechanism_used": build_diagnostics.get("build_mechanism_used"),
            "build_valid": build_diagnostics.get("build_valid"),
            "flowsheet_verification": build_diagnostics.get("flowsheet_verification", {}),
        },
        "simulation": {
            "status": simulation_diagnostics.get("status"),
            "passed": simulation_diagnostics.get("passed"),
            "run_status": simulation_diagnostics.get("run_status"),
            "results_status": simulation_diagnostics.get("results_status"),
            "simulation_time_seconds": simulation_diagnostics.get("simulation_time_seconds"),
            "summary": simulation_diagnostics.get("summary"),
            "issues": simulation_diagnostics.get("issues", []),
        },
        "kpis": kpis,
        "acceptance": acceptance,
        "environment": environment,
        "failure_classification": failure_classification,
        "generated_files": result.generated_files,
    }

    summary_path = layout.run_dir / "live_aspen_summary.json"
    _write_json(summary_path, summary)
    _write_json(LIVE_RESULTS_ROOT / "latest_live_aspen_summary.json", summary | {"summary_path": str(summary_path)})
    (LIVE_RESULTS_ROOT / "latest_live_aspen_analysis.md").write_text(markdown + "\n", encoding="utf-8")
    return analysis_path, summary_path, summary


def test_live_aspen_failure_classifier_identifies_appanywhere_localization_issue() -> None:
    fake_result = SimpleNamespace(
        status="build_failed",
        error=(
            "COM block builder failed: Unable to create block 'MIX-FEED' as 'MIXER'. "
            "AspenTech.AspenPlus.Localization could not be loaded by PresentationFramework."
        ),
        details={},
    )

    classification = _classify_live_aspen_failure(
        fake_result,
        build_diagnostics={"build_mode": "auto", "build_mechanism_used": "com_block_builder"},
        simulation_diagnostics={"status": "build_failed"},
        environment={"suspected_appanywhere_virtualization": True},
    )

    assert classification["category"] == "appanywhere_virtualization_dependency"
    assert classification["appanywhere_context_detected"] is True
    assert "AppAnywhere" in classification["recommended_action"]


def test_process_library_methanol_live_aspen_run() -> None:
    _require_live_aspen_ready()

    result = run_process(
        METHANOL_PROCESS_DIR,
        LIVE_RESULTS_ROOT / "process_runs",
        visible=_env_flag("ASPEN_PLUS_VISIBLE", default=False),
        build_mode="auto",
        timeout_seconds=1800,
        build_timeout_seconds=180,
        report_format="html",
    )
    analysis_path, summary_path, summary_payload = _persist_live_analysis(result)

    failure_context = json.dumps(
        {
            "error": result.error,
            "details": result.details,
            "analysis_path": str(analysis_path) if analysis_path else None,
            "summary_path": str(summary_path) if summary_path else None,
            "environment": summary_payload.get("environment", {}),
            "failure_classification": summary_payload.get("failure_classification", {}),
        },
        indent=2,
        default=str,
    )
    assert result.succeeded, f"{result.status}: {result.error}\n{failure_context}"
    assert result.status == "succeeded"
    assert result.layout is not None
    assert result.report_dir is not None
    assert analysis_path is not None and analysis_path.is_file()
    assert summary_path is not None and summary_path.is_file()

    assert result.layout.generated_inp_path.is_file()
    assert result.layout.generated_inp_path.stat().st_size > 0
    assert result.layout.output_apw_path.is_file()
    assert result.report_dir.is_dir()

    expected_results = {
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
    assert expected_results.issubset({path.name for path in result.layout.results_dir.iterdir()})

    build_diagnostics = json.loads((result.layout.results_dir / "build_diagnostics.json").read_text(encoding="utf-8"))
    acceptance = json.loads((result.layout.results_dir / "acceptance.json").read_text(encoding="utf-8"))
    diagnostics = json.loads((result.layout.results_dir / "simulation_diagnostics.json").read_text(encoding="utf-8"))
    artifact_paths, tables = load_result_artifact_tables(result)

    assert build_diagnostics["status"] == "build_verified"
    assert build_diagnostics["build_valid"] is True
    assert build_diagnostics["build_mode"] == "auto"
    assert build_diagnostics["build_mechanism_used"] == "com_block_builder"
    assert "isolated_inp_import_worker" not in json.dumps(build_diagnostics, default=str)
    assert "legacy Aspen INP import path" not in json.dumps(build_diagnostics, default=str)

    assert "passed" in acceptance
    assert acceptance["passed"] is True
    assert diagnostics["passed"] is True
    assert diagnostics["status"] == "succeeded"
    assert diagnostics["run_status"] == "converged"
    assert diagnostics["results_status"] == "readable"

    assert set(artifact_paths) == {"streams", "blocks", "material_balance", "energy_balance"}
    assert not tables["streams"].empty
    assert not tables["blocks"].empty
    assert not tables["material_balance"].empty
    assert not tables["energy_balance"].empty
    assert {"stream_name", "temperature", "pressure", "mass_flow", "mole_flow"}.issubset(tables["streams"].columns)
    assert {"block_name", "block_type", "duty", "duty_kw", "duty_mw", "net_work_kw"}.issubset(tables["blocks"].columns)
    assert {"component", "input_kmol_hr", "output_kmol_hr", "closure_pct"}.issubset(
        tables["material_balance"].columns
    )
    assert {"block_name", "duty", "duty_kw", "duty_mw"}.issubset(tables["energy_balance"].columns)

    analysis_text = analysis_path.read_text(encoding="utf-8")
    assert "Codex Session Analysis: `methanol`" in analysis_text
    assert "Use the CSV artifacts below as the source of truth" in analysis_text
    assert "Acceptance status from `acceptance.json`: True." in analysis_text
