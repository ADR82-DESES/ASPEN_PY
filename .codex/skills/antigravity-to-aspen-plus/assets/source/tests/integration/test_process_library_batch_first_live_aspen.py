from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from aspen_automation import generate_inp, load_spec, run_aspen_batch, run_process_batch_first
from aspen_automation.session import check_aspen_running


ROOT = Path(__file__).resolve().parents[2]
METHANOL_PROCESS_DIR = ROOT / "process_library" / "methanol"
LIVE_RESULTS_ROOT = ROOT / "test_results" / "live_aspen_batch_first"


def _require_live_batch_ready(*, needs_com: bool = False) -> None:
    if os.environ.get("ASPEN_PLUS_INTEGRATION") != "1":
        pytest.skip("Set ASPEN_PLUS_INTEGRATION=1 to run live Aspen Plus batch-first tests")
    if not (METHANOL_PROCESS_DIR / "process.yaml").is_file():
        pytest.fail(f"Canonical methanol process YAML was not found: {METHANOL_PROCESS_DIR / 'process.yaml'}")
    if needs_com and not check_aspen_running():
        pytest.fail("AspenPlus.exe is not running; launch Aspen Plus V14 before the BKP load/extraction gate.")


def test_live_methanol_generated_inp_batch_translator_accepts(tmp_path: Path) -> None:
    _require_live_batch_ready()

    spec = load_spec(str(METHANOL_PROCESS_DIR / "process.yaml"))
    inp_path = tmp_path / "methanol_generated.inp"
    generate_inp(spec, output_path=str(inp_path))

    result = run_aspen_batch(inp_path, tmp_path / "batch", run_id="methanol", timeout_seconds=1800)

    assert result.succeeded, json.dumps(result.to_diagnostics(), indent=2, default=str)
    assert result.archive_path is not None
    assert result.history_diagnostics["status"] == "converged"


def test_live_methanol_batch_first_bkp_loads_and_extracts_results() -> None:
    _require_live_batch_ready(needs_com=True)

    result = run_process_batch_first(
        METHANOL_PROCESS_DIR,
        LIVE_RESULTS_ROOT / "process_runs",
        visible=os.environ.get("ASPEN_PLUS_VISIBLE", "").strip().lower() in {"1", "true", "yes"},
        enforce_acceptance_targets=False,
        timeout_seconds=1800,
        batch_timeout_seconds=1800,
        report_format="html",
    )

    failure_context = json.dumps(
        {
            "status": result.status,
            "error": result.error,
            "details": result.details,
        },
        indent=2,
        default=str,
    )
    assert result.succeeded, failure_context
    assert result.layout is not None
    assert result.layout.results_dir.joinpath("context_probe.json").is_file()
    build_diagnostics = json.loads(
        result.layout.results_dir.joinpath("build_diagnostics.json").read_text(encoding="utf-8")
    )
    simulation_diagnostics = json.loads(
        result.layout.results_dir.joinpath("simulation_diagnostics.json").read_text(encoding="utf-8")
    )
    batch_engine = build_diagnostics.get("batch_engine", {})
    artifacts = batch_engine.get("artifacts", {}) if isinstance(batch_engine, dict) else {}
    summary_path = result.layout.run_dir / "live_aspen_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "status": result.status,
                "error": result.error,
                "run_dir": str(result.layout.run_dir),
                "generated_inp_path": str(result.layout.generated_inp_path),
                "context_probe_path": str(result.layout.results_dir / "context_probe.json"),
                "history_path": artifacts.get(".his", {}).get("path"),
                "stdout_path": batch_engine.get("stdout_path"),
                "stderr_path": batch_engine.get("stderr_path"),
                "build": build_diagnostics,
                "simulation": simulation_diagnostics,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    assert build_diagnostics["build_mode"] == "batch-first"
    assert build_diagnostics["history_diagnostics"]["status"] == "converged"
    assert simulation_diagnostics["status"] == "succeeded"
    assert simulation_diagnostics["results_status"] == "readable"
    assert simulation_diagnostics["acceptance_targets_enforced"] is False
    assert summary_path.is_file()
