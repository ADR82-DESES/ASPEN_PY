from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd

from aspen_automation.process_library import (
    BkpExtractionResult,
    _build_batch_first_diagnostics,
    _build_simulation_diagnostics,
    discover_processes,
    load_process_spec,
    run_process,
    run_process_batch_first,
    run_process_library,
    scan_process_library,
    validate_process_spec_file,
)
from aspen_automation.batch_engine import AspenBatchResult
from aspen_automation.process_spec_coherence import analyze_process_spec_coherence
from aspen_automation.exceptions import BuildError
from aspen_automation.session import SessionResult


ROOT = Path(__file__).resolve().parents[2]
METHANOL_TEMPLATE_PATH = ROOT / "templates" / "methanol_plant_atr.yaml"
PROCESS_LIBRARY_ROOT = ROOT / "process_library"
NOTEBOOK_PATH = ROOT / "notebooks" / "process_library_runner.ipynb"
METHANOL_NOTEBOOK_PATH = ROOT / "notebooks" / "methanol_example_runner.ipynb"


def _make_test_workspace(prefix: str) -> Path:
    workspace = ROOT / "test_results" / f"{prefix}_{uuid.uuid4().hex}"
    workspace.mkdir(parents=True, exist_ok=False)
    return workspace


def _write_yaml_from_template(target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(METHANOL_TEMPLATE_PATH.read_text(encoding="utf-8"), encoding="utf-8")


def test_process_library_methanol_spec_validates() -> None:
    report = validate_process_spec_file(PROCESS_LIBRARY_ROOT / "methanol" / "process.yaml")
    assert report["valid"], report["errors"]


def test_process_library_methanol_spec_uses_rigorous_final_column_without_purification_warning() -> None:
    spec = load_process_spec(PROCESS_LIBRARY_ROOT / "methanol")
    coherence = analyze_process_spec_coherence(spec)
    assert coherence["passed"] is True
    messages = [issue["message"] for issue in coherence["issues"] if issue["severity"] == "warning"]
    assert not any("High-purity target" in message for message in messages)
    assert not any("Property method" in message for message in messages)
    assert not any("binary-parameter provenance is missing" in message for message in messages)
    syn_block = next(block for block in spec["blocks"] if block["name"] == "B-SYN")
    degas_block = next(block for block in spec["blocks"] if block["name"] == "B-DEGAS")
    dist_block = next(block for block in spec["blocks"] if block["name"] == "B-DIST")
    assert syn_block["type"] == "RPLUG"
    assert syn_block["parameters"]["LENGTH"] == 21.3
    assert degas_block["type"] == "FLASH2"
    assert degas_block["parameters"]["TEMP"] == 80.0
    assert dist_block["type"] == "RADFRAC"
    assert dist_block["radfrac"]["bottoms_rate"] == 82000.0
    assert next(block for block in spec["blocks"] if block["name"] == "B-LCOOL")["type"] == "HEATER"
    assert next(block for block in spec["blocks"] if block["name"] == "B-LFLA")["type"] == "FLASH2"
    assert next(block for block in spec["blocks"] if block["name"] == "MIX-COL")["type"] == "MIXER"
    assert next(block for block in spec["blocks"] if block["name"] == "B-PDEG")["type"] == "FLASH2"
    assert next(block for block in spec["blocks"] if block["name"] == "MIX-VENT")["type"] == "MIXER"
    degas_connection = next(item for item in spec["flowsheet"] if item["block"] == "B-DEGAS")
    assert degas_connection["outputs"] == ["LIGHTS", "CLIQ-RAW"]
    recovery_flash = next(item for item in spec["flowsheet"] if item["block"] == "B-LFLA")
    assert recovery_flash["outputs"] == ["VENT-GAS", "REC-MEOH"]
    mix_connection = next(item for item in spec["flowsheet"] if item["block"] == "MIX-COL")
    assert mix_connection["inputs"] == ["CLIQ-RAW", "REC-MEOH"]
    dist_connection = next(item for item in spec["flowsheet"] if item["block"] == "B-DIST")
    assert dist_connection["inputs"] == ["CRUDE-LQ"]
    assert dist_connection["outputs"] == ["MEOH-RAW", "WASTE-H2O"]
    product_degas_connection = next(item for item in spec["flowsheet"] if item["block"] == "B-PDEG")
    assert product_degas_connection["outputs"] == ["PRO-VENT", "MEOH-PRO"]
    vent_mix_connection = next(item for item in spec["flowsheet"] if item["block"] == "MIX-VENT")
    assert vent_mix_connection["inputs"] == ["VENT-GAS", "PRO-VENT"]
    assert vent_mix_connection["outputs"] == ["VENT-TOT"]
    assert spec["targets"]["product_conditions"][0]["pressure"] == 1.5
    assert spec["targets"]["component_loss_limits"][0]["stream"] == "VENT-TOT"
    assert spec["targets"]["component_loss_limits"][0]["component"] == "CH3OH"
    assert not any("equilibrium reactor model" in message for message in messages)


def test_batch_first_diagnostics_promote_nrtl_model_quality_warning() -> None:
    spec = load_process_spec(PROCESS_LIBRARY_ROOT / "methanol")
    batch_result = AspenBatchResult(
        engine_path=None,
        command=["aspen"],
        batch_dir=".",
        input_path="run.inp",
        run_id="run",
        returncode=0,
        timed_out=False,
        elapsed_seconds=1.0,
        stdout_path="stdout.txt",
        stderr_path="stderr.txt",
        artifacts={
            ".bkp": {"exists": True, "path": "run.bkp"},
            ".his": {"exists": True, "path": "run.his"},
        },
        history_diagnostics={
            "status": "converged",
            "input_translation_failed": False,
            "summary_counts": {},
            "messages": [
                {
                    "severity": "warning",
                    "message": "NRTL BINARY PARAMETERS FOR ALL COMPONENT PAIRS ARE ZERO.",
                }
            ],
        },
    )

    diagnostics = _build_batch_first_diagnostics(batch_result, Path("run.inp"), spec)

    assert diagnostics["nrtl_binary_parameters_status"] == "warning_from_aspen"
    assert diagnostics["model_quality_warnings"] == [
        "NRTL BINARY PARAMETERS FOR ALL COMPONENT PAIRS ARE ZERO."
    ]


def test_simulation_diagnostics_block_post_com_nrtl_warning_when_acceptance_enforced() -> None:
    spec = load_process_spec(PROCESS_LIBRARY_ROOT / "methanol")
    session_result = SessionResult(convergence_status="converged", simulation_time_seconds=1.0)
    session_result.diagnostics.update({"build_valid": True, "flowsheet_verification": {"build_valid": True}})
    results = {
        "streams": pd.DataFrame(
            [
                {"stream_name": "VENT-GAS", "mass_flow": 75000.0, "CH3OH_mass_frac": 0.30},
                {"stream_name": "MEOH-PRO", "mass_flow": 412100.0, "pressure": 1.5, "CH3OH_mass_frac": 0.9995},
            ]
        ),
        "blocks": pd.DataFrame([{"block_name": "B-DIST", "block_type": "RADFRAC", "duty_kw": 1.0}]),
        "material_balance": pd.DataFrame([{"component": "CH3OH", "feed": 1.0, "product": 1.0}]),
        "energy_balance": pd.DataFrame([{"block_name": "B-DIST", "duty_kw": 1.0}]),
        "kpis": {
            "convergence_status": "converged",
            "production_rate_tpd": 10000.0,
            "purity_fraction": 0.9995,
        },
        "diagnostics": {"convergence_status": "converged"},
    }
    acceptance = {
        "passed": True,
        "checks": [{"name": "Convergence", "passed": True}],
        "component_loss_checks": [],
        "lights_recovery": {},
    }
    build_diagnostics = {
        "history_diagnostics": {"status": "converged", "messages": []},
        "batch_history_diagnostics": {"status": "converged", "messages": []},
        "post_com_history_diagnostics": {
            "status": "converged",
            "summary_counts": {"warnings": {"physical_property": 1}},
            "messages": [
                {
                    "severity": "warning",
                    "message": "NRTL BINARY PARAMETERS FOR ALL COMPONENT PAIRS ARE ZERO.",
                }
            ],
        },
    }

    diagnostics = _build_simulation_diagnostics(
        spec,
        session_result,
        results,
        acceptance,
        enforce_acceptance_targets=True,
        require_balance_tables=True,
        build_diagnostics=build_diagnostics,
    )

    assert diagnostics["passed"] is False
    assert diagnostics["status"] == "model_quality_failed"
    assert diagnostics["nrtl_binary_parameters_status"] == "warning_from_post_com"
    assert diagnostics["post_com_history_diagnostics"]["status"] == "converged"


def test_scan_process_library_discovers_valid_and_invalid_processes(tmp_path: Path) -> None:
    library_root = tmp_path / "process_library"
    _write_yaml_from_template(library_root / "methanol" / "process.yaml")

    (library_root / "ammonia").mkdir(parents=True, exist_ok=True)

    hydrogen_dir = library_root / "hydrogen"
    hydrogen_dir.mkdir(parents=True, exist_ok=True)
    _write_yaml_from_template(hydrogen_dir / "one.yaml")
    _write_yaml_from_template(hydrogen_dir / "two.yaml")

    scan = scan_process_library(library_root)

    assert [process.name for process in scan.processes] == ["methanol"]
    assert {issue.process_name for issue in scan.issues} == {"ammonia", "hydrogen"}
    assert discover_processes(library_root)[0].spec_path.name == "process.yaml"


def test_run_process_writes_outputs_to_process_specific_run_dir() -> None:
    workspace = _make_test_workspace("run_process_outputs")
    try:
        library_root = workspace / "process_library"
        process_dir = library_root / "methanol"
        _write_yaml_from_template(process_dir / "process.yaml")
        runs_root = workspace / "process_runs"

        fake_aspen = MagicMock(name="aspen")
        fake_session_result = SimpleNamespace(
            build_mode="auto",
            build_mechanism_used="com_block_builder",
            build_fallback_attempted=False,
            diagnostics={
                "build_valid": True,
                "flowsheet_verification": {
                    "build_valid": True,
                    "stream_count": 3,
                    "block_count": 2,
                    "stream_samples": ["NG-FEED", "STEAM", "O2-FEED"],
                    "block_samples": ["MIX-FEED", "B-ATR"],
                },
            },
            convergence_status="converged",
            simulation_time_seconds=12.5,
            aspen=fake_aspen,
        )
        fake_results = {
            "streams": pd.DataFrame([{"stream_name": "NG-FEED", "temperature": 40.0}]),
            "blocks": pd.DataFrame([{"block_name": "B-ATR", "block_type": "RGIBBS", "duty_kw": 10.0}]),
            "material_balance": pd.DataFrame([{"component": "CH4", "closure_pct": -1.5}]),
            "energy_balance": pd.DataFrame([{"block_name": "TOTAL", "duty_mw": 12.3}]),
            "kpis": {
                "production_rate_tpd": 10000.0,
                "purity_fraction": 0.9985,
                "convergence_status": "converged",
            },
            "diagnostics": {"convergence_status": "converged", "per_error": 0},
        }

        with patch(
            "aspen_automation.process_library.run_simulation_session",
            return_value=fake_session_result,
        ) as mock_run_session, patch(
            "aspen_automation.process_library.extract_results",
            return_value=fake_results,
        ), patch(
            "aspen_automation.process_library.analyze_process_spec_coherence",
            return_value={"passed": True, "issues": []},
        ):
            result = run_process(process_dir, runs_root, visible=False)

        assert result.succeeded
        mock_run_session.assert_called_once()
        assert mock_run_session.call_args.kwargs["build_mode"] == "auto"
        assert result.layout is not None
        assert result.layout.generated_inp_path.is_file()
        build_diagnostics = json.loads(result.layout.results_dir.joinpath("build_diagnostics.json").read_text(encoding="utf-8"))
        assert build_diagnostics["build_mode"] == "auto"
        assert build_diagnostics["build_mechanism_used"] == "com_block_builder"
        assert build_diagnostics["flowsheet_verification"]["stream_count"] == 3
        assert build_diagnostics["flowsheet_verification"]["block_count"] == 2
        assert result.layout.results_dir.joinpath("streams.csv").is_file()
        assert result.layout.results_dir.joinpath("blocks.csv").is_file()
        assert result.layout.results_dir.joinpath("material_balance.csv").is_file()
        assert result.layout.results_dir.joinpath("energy_balance.csv").is_file()
        assert result.layout.results_dir.joinpath("kpis.json").is_file()
        assert result.layout.results_dir.joinpath("acceptance.json").is_file()
        assert result.layout.results_dir.joinpath("diagnostics.json").is_file()
        assert result.layout.results_dir.joinpath("simulation_diagnostics.json").is_file()
        assert result.layout.output_apw_path == result.layout.run_dir / "methanol_output.apw"
        fake_aspen.SaveAs.assert_called_once_with(str(result.layout.output_apw_path))
        acceptance = json.loads(result.layout.results_dir.joinpath("acceptance.json").read_text(encoding="utf-8"))
        assert "passed" in acceptance
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_run_process_passes_explicit_com_auto_without_remapping() -> None:
    workspace = _make_test_workspace("run_process_com_auto")
    try:
        library_root = workspace / "process_library"
        process_dir = library_root / "methanol"
        _write_yaml_from_template(process_dir / "process.yaml")
        runs_root = workspace / "process_runs"

        build_error = BuildError(
            "legacy INP import failed",
            build_mode="com-auto",
            mechanism_tried="isolated_inp_import_worker",
            diagnostics={
                "build_valid": False,
                "flowsheet_verification": {
                    "build_valid": False,
                    "stream_count": 0,
                    "block_count": 0,
                    "stream_samples": [],
                    "block_samples": [],
                },
            },
        )

        with patch(
            "aspen_automation.process_library.run_simulation_session",
            side_effect=build_error,
        ) as mock_run_session, patch(
            "aspen_automation.process_library.analyze_process_spec_coherence",
            return_value={"passed": True, "issues": []},
        ):
            result = run_process(process_dir, runs_root, visible=False, build_mode="com-auto")

        mock_run_session.assert_called_once()
        assert mock_run_session.call_args.kwargs["build_mode"] == "com-auto"
        assert result.status == "build_failed"
        assert result.layout is not None
        assert result.layout.generated_inp_path.is_file()
        build_diagnostics = json.loads(result.layout.results_dir.joinpath("build_diagnostics.json").read_text(encoding="utf-8"))
        assert build_diagnostics["build_mode"] == "com-auto"
        assert build_diagnostics["build_mechanism_used"] == "isolated_inp_import_worker"
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_run_process_batch_first_uses_batch_and_bkp_loader_without_auto_session() -> None:
    workspace = _make_test_workspace("run_process_batch_first")
    try:
        library_root = workspace / "process_library"
        process_dir = library_root / "methanol"
        _write_yaml_from_template(process_dir / "process.yaml")
        runs_root = workspace / "process_runs"
        archive_path = workspace / "compiled.bkp"
        archive_path.write_text("backup", encoding="utf-8")
        fake_batch = AspenBatchResult(
            engine_path="aspen.exe",
            command=["aspen.exe", "methanol", "methanol", "/mmbackup", "/log"],
            batch_dir=str(workspace),
            input_path=str(workspace / "methanol.inp"),
            run_id="methanol",
            returncode=0,
            timed_out=False,
            elapsed_seconds=2.0,
            stdout_path=str(workspace / "stdout.txt"),
            stderr_path=str(workspace / "stderr.txt"),
            artifacts={".bkp": {"path": str(archive_path), "exists": True}},
            history_diagnostics={
                "status": "converged",
                "input_translation_failed": False,
                "summary_counts": {},
                "messages": [],
            },
        )
        fake_session = SessionResult(
            convergence_status="converged",
            build_mode="batch-first",
            build_mechanism_used="InitFromArchive2",
            simulation_time_seconds=9.0,
            diagnostics={
                "build_valid": True,
                "flowsheet_verification": {"build_valid": True},
                "convergence_status": "converged",
                "per_error": 0,
            },
        )
        fake_results = {
            "streams": pd.DataFrame([{"stream_name": "NG-FEED", "temperature": 40.0, "mass_flow": 1.0}]),
            "blocks": pd.DataFrame([{"block_name": "B-ATR", "block_type": "RGIBBS", "duty_kw": 10.0}]),
            "material_balance": pd.DataFrame(
                [{"component": "CH4", "input_kmol_hr": 1.0, "output_kmol_hr": 0.99, "closure_pct": -1.0}]
            ),
            "energy_balance": pd.DataFrame([{"block_name": "B-ATR", "duty_mw": 1.0}]),
            "kpis": {"convergence_status": "converged"},
            "diagnostics": {"convergence_status": "converged", "per_error": 0},
        }

        def _fake_bkp_load(spec, bkp_path, layout, **kwargs):
            assert bkp_path == str(archive_path)
            layout.results_dir.joinpath("context_probe.json").write_text(
                json.dumps({"process_ancestry": {"status": "collected"}}),
                encoding="utf-8",
            )
            return BkpExtractionResult(
                session_result=fake_session,
                results=fake_results,
                context_probe={"process_ancestry": {"status": "collected"}},
            )

        with patch(
            "aspen_automation.process_library.run_aspen_batch",
            return_value=fake_batch,
        ) as mock_batch, patch(
            "aspen_automation.process_library.load_bkp_and_extract_results",
            side_effect=_fake_bkp_load,
        ) as mock_bkp_load, patch(
            "aspen_automation.process_library.run_simulation_session",
        ) as mock_run_session, patch(
            "aspen_automation.session.build_flowsheet_via_com",
        ) as mock_com_builder, patch(
            "aspen_automation.process_library.analyze_process_spec_coherence",
            return_value={"passed": True, "issues": []},
        ):
            result = run_process_batch_first(process_dir, runs_root, visible=False)

        assert result.succeeded
        mock_batch.assert_called_once()
        mock_bkp_load.assert_called_once()
        mock_run_session.assert_not_called()
        mock_com_builder.assert_not_called()
        assert result.layout is not None
        build_diagnostics = json.loads(result.layout.results_dir.joinpath("build_diagnostics.json").read_text(encoding="utf-8"))
        simulation_diagnostics = json.loads(
            result.layout.results_dir.joinpath("simulation_diagnostics.json").read_text(encoding="utf-8")
        )
        acceptance = json.loads(result.layout.results_dir.joinpath("acceptance.json").read_text(encoding="utf-8"))
        assert build_diagnostics["build_mode"] == "batch-first"
        assert build_diagnostics["build_mechanism_used"] == "aspen_batch+InitFromArchive2"
        assert build_diagnostics["history_diagnostics"]["status"] == "converged"
        assert simulation_diagnostics["status"] == "succeeded"
        assert simulation_diagnostics["acceptance_targets_enforced"] is False
        assert acceptance["passed"] is False
        assert result.layout.results_dir.joinpath("context_probe.json").is_file()
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def test_run_process_batch_first_rejects_conflicting_debug_spec_path(tmp_path: Path) -> None:
    library_root = tmp_path / "process_library"
    process_dir = library_root / "methanol"
    _write_yaml_from_template(process_dir / "process.yaml")
    mismatch = tmp_path / "other.yaml"
    _write_yaml_from_template(mismatch)

    result = run_process_batch_first(
        process_dir,
        tmp_path / "process_runs",
        spec_path=mismatch,
    )

    assert result.status == "discovery_failed"
    assert result.succeeded is False
    assert "process_dir as the canonical input" in str(result.error)


def test_run_process_blocks_when_coherence_fails(tmp_path: Path) -> None:
    library_root = tmp_path / "process_library"
    process_dir = library_root / "methanol"
    _write_yaml_from_template(process_dir / "process.yaml")
    process_yaml = process_dir / "process.yaml"
    process_yaml.write_text(
        process_yaml.read_text(encoding="utf-8").replace("fraction: 0.05", "fraction: 0.10", 1),
        encoding="utf-8",
    )
    runs_root = tmp_path / "process_runs"

    result = run_process(process_dir, runs_root, visible=False)

    assert result.status == "coherence_failed"
    assert result.succeeded is False
    assert result.layout is not None
    assert result.layout.results_dir.joinpath("coherence_report.json").is_file()
    coherence = json.loads(result.layout.results_dir.joinpath("coherence_report.json").read_text(encoding="utf-8"))
    assert coherence["passed"] is False


def test_run_process_flags_unreadable_results_after_converged_session(tmp_path: Path) -> None:
    library_root = tmp_path / "process_library"
    process_dir = library_root / "methanol"
    _write_yaml_from_template(process_dir / "process.yaml")
    runs_root = tmp_path / "process_runs"

    fake_aspen = MagicMock(name="aspen")
    fake_session_result = SimpleNamespace(
        build_mode="auto",
        build_mechanism_used="InitFromFile2",
        build_fallback_attempted=False,
        diagnostics={"convergence_status": "converged", "per_error": 0},
        convergence_status="converged",
        simulation_time_seconds=7.5,
        aspen=fake_aspen,
    )
    unreadable_results = {
        "streams": pd.DataFrame([{"stream_name": "NG-FEED", "temperature": None, "pressure": None}]),
        "blocks": pd.DataFrame([{"block_name": "B-ATR", "block_type": "RGIBBS", "duty_kw": None}]),
        "material_balance": pd.DataFrame(),
        "energy_balance": pd.DataFrame(),
        "kpis": {
            "production_rate_tpd": None,
            "purity_fraction": None,
            "convergence_status": "unknown",
        },
        "diagnostics": {"convergence_status": "unknown", "per_error": None},
    }

    with patch(
        "aspen_automation.process_library.run_simulation_session",
        return_value=fake_session_result,
    ), patch(
        "aspen_automation.process_library.extract_results",
        return_value=unreadable_results,
    ), patch(
        "aspen_automation.process_library.analyze_process_spec_coherence",
        return_value={"passed": True, "issues": []},
    ):
        result = run_process(process_dir, runs_root, visible=False)

    assert result.status == "results_unreadable"
    assert result.succeeded is False
    assert result.layout is not None
    simulation_diagnostics = json.loads(
        result.layout.results_dir.joinpath("simulation_diagnostics.json").read_text(encoding="utf-8")
    )
    assert simulation_diagnostics["status"] == "results_unreadable"
    assert simulation_diagnostics["stream_numeric_rows"] == 0
    assert simulation_diagnostics["block_numeric_rows"] == 0
    assert result.layout.results_dir.joinpath("yaml_update_suggestions.json").is_file()


def test_run_process_flags_empty_flowsheet_as_build_failed(tmp_path: Path) -> None:
    library_root = tmp_path / "process_library"
    process_dir = library_root / "methanol"
    _write_yaml_from_template(process_dir / "process.yaml")
    runs_root = tmp_path / "process_runs"

    build_error = BuildError(
        "Aspen import did not materialize a usable flowsheet.",
        build_mode="auto",
        mechanism_tried="Import",
        diagnostics={
            "build_valid": False,
            "generated_inp_path": "temp_simulation.inp",
            "generated_inp_file": {"path": "temp_simulation.inp", "exists": False, "size_bytes": None},
            "aspen_preflight": {
                "v14_verified": True,
                "aspen_version": "40.0",
                "preflight_status": "v14_connected",
            },
            "flowsheet_verification": {
                "build_valid": False,
                "stream_count": 0,
                "block_count": 0,
                "stream_samples": [],
                "block_samples": [],
            },
            "import_attempts": [
                {"mechanism": "Import", "path_variant": "raw_string", "success": False, "error": "empty tree"},
                {
                    "mechanism": "InitFromFile2",
                    "path_variant": "raw_string",
                    "success": False,
                    "error": "Unable to open file",
                },
            ],
            "per_error": 0,
        },
    )

    with patch(
        "aspen_automation.process_library.run_simulation_session",
        side_effect=build_error,
    ), patch(
        "aspen_automation.process_library.analyze_process_spec_coherence",
        return_value={"passed": True, "issues": []},
    ):
        result = run_process(process_dir, runs_root, visible=False)

    assert result.status == "build_failed"
    assert result.succeeded is False
    assert result.layout is not None
    build_diagnostics = json.loads(result.layout.results_dir.joinpath("build_diagnostics.json").read_text(encoding="utf-8"))
    assert build_diagnostics["status"] == "build_failed"
    assert build_diagnostics["build_valid"] is False
    assert build_diagnostics["diagnostics"]["aspen_preflight"]["v14_verified"] is True
    assert build_diagnostics["diagnostics"]["import_attempts"][1]["error"] == "Unable to open file"
    simulation_diagnostics = json.loads(
        result.layout.results_dir.joinpath("simulation_diagnostics.json").read_text(encoding="utf-8")
    )
    assert simulation_diagnostics["status"] == "build_failed"
    assert simulation_diagnostics["run_status"] == "not_started"
    assert simulation_diagnostics["session_diagnostics"]["aspen_preflight"]["aspen_version"] == "40.0"


def test_run_process_reports_soft_connection_failure_without_generic_runtime_error(tmp_path: Path) -> None:
    library_root = tmp_path / "process_library"
    process_dir = library_root / "methanol"
    _write_yaml_from_template(process_dir / "process.yaml")
    runs_root = tmp_path / "process_runs"

    fake_session_result = SimpleNamespace(
        build_mode="auto",
        build_mechanism_used="none",
        build_fallback_attempted=False,
        diagnostics={
            "error": "Aspen Plus V14 connection check failed during InitNew(): license unavailable",
            "connection_error_type": "AspenConnectionError",
            "aspen_connection_verified": False,
            "aspen_preflight": {
                "connection_verified": False,
                "v14_verified": False,
                "v14_version_verified": False,
                "version_status": "unreported",
                "preflight_status": "init_failed",
                "aspen_version": None,
            },
        },
        convergence_status="failed",
        simulation_time_seconds=0.0,
        aspen=None,
    )

    with patch(
        "aspen_automation.process_library.run_simulation_session",
        return_value=fake_session_result,
    ), patch(
        "aspen_automation.process_library.analyze_process_spec_coherence",
        return_value={"passed": True, "issues": []},
    ):
        result = run_process(process_dir, runs_root, visible=False)

    assert result.status == "connection_failed"
    assert result.succeeded is False
    assert result.error == fake_session_result.diagnostics["error"]
    assert result.layout is not None

    build_diagnostics = json.loads(result.layout.results_dir.joinpath("build_diagnostics.json").read_text(encoding="utf-8"))
    assert build_diagnostics["status"] == "connection_failed"
    assert build_diagnostics["build_valid"] is False
    assert build_diagnostics["diagnostics"]["aspen_preflight"]["preflight_status"] == "init_failed"

    simulation_diagnostics = json.loads(
        result.layout.results_dir.joinpath("simulation_diagnostics.json").read_text(encoding="utf-8")
    )
    assert simulation_diagnostics["status"] == "connection_failed"
    assert simulation_diagnostics["summary"] == fake_session_result.diagnostics["error"]
    assert simulation_diagnostics["run_status"] == "not_started"
    assert simulation_diagnostics["session_diagnostics"]["connection_error_type"] == "AspenConnectionError"


def test_run_process_writes_safe_yaml_update_proposal_for_high_confidence_runtime_issue(tmp_path: Path) -> None:
    library_root = tmp_path / "process_library"
    process_dir = library_root / "methanol"
    _write_yaml_from_template(process_dir / "process.yaml")
    runs_root = tmp_path / "process_runs"

    fake_aspen = MagicMock(name="aspen")
    fake_session_result = SimpleNamespace(
        build_mode="auto",
        build_mechanism_used="InitFromFile2",
        build_fallback_attempted=False,
        diagnostics={"convergence_status": "converged", "per_error": 0},
        convergence_status="converged",
        simulation_time_seconds=10.0,
        aspen=fake_aspen,
    )
    partial_results = {
        "streams": pd.DataFrame([{"stream_name": "MEOH-PRO", "temperature": 35.0, "mass_flow": 1000.0}]),
        "blocks": pd.DataFrame([{"block_name": "B-ATR", "block_type": "RGIBBS", "duty_kw": 10.0}]),
        "material_balance": pd.DataFrame(),
        "energy_balance": pd.DataFrame(),
        "kpis": {
            "production_rate_tpd": 10000.0,
            "purity_fraction": None,
            "convergence_status": "converged",
        },
        "diagnostics": {"convergence_status": "converged", "per_error": 0},
    }
    coherence_report = {
        "passed": True,
        "issues": [
            {
                "severity": "warning",
                "location": "properties.databanks",
                "message": "No explicit databanks are configured, so the run will fall back to defaults.",
                "suggestion": "Declare the databanks explicitly in YAML so the property environment is intentional and reproducible.",
            }
        ],
    }

    with patch(
        "aspen_automation.process_library.run_simulation_session",
        return_value=fake_session_result,
    ), patch(
        "aspen_automation.process_library.extract_results",
        return_value=partial_results,
    ), patch(
        "aspen_automation.process_library.analyze_process_spec_coherence",
        return_value=coherence_report,
    ):
        result = run_process(process_dir, runs_root, visible=False)

    assert result.status == "results_incomplete"
    assert result.succeeded is False
    assert result.layout is not None
    suggestion_artifact = json.loads(
        result.layout.results_dir.joinpath("yaml_update_suggestions.json").read_text(encoding="utf-8")
    )
    assert suggestion_artifact["generated_yaml"] is True
    proposal_path = result.layout.results_dir / "process_update_proposal.yaml"
    assert proposal_path.is_file()
    proposal_text = proposal_path.read_text(encoding="utf-8")
    assert "databanks:" in proposal_text
    assert "APV140 PURE32" in proposal_text


def test_run_process_library_continues_after_failure(tmp_path: Path) -> None:
    library_root = tmp_path / "process_library"
    _write_yaml_from_template(library_root / "methanol" / "process.yaml")
    _write_yaml_from_template(library_root / "ammonia" / "process.yaml")

    def _fake_run(process_dir: Path, runs_root: Path, **_: object):
        name = Path(process_dir).name
        if name == "methanol":
            return SimpleNamespace(process_name=name, succeeded=False, status="failed", error="boom")
        return SimpleNamespace(process_name=name, succeeded=True, status="succeeded", error=None)

    with patch("aspen_automation.process_library.run_process", side_effect=_fake_run):
        results = run_process_library(library_root, tmp_path / "process_runs", continue_on_error=True)

    assert [result.process_name for result in results] == ["ammonia", "methanol"]
    assert {result.status for result in results} == {"failed", "succeeded"}


def test_process_library_notebook_has_required_sections() -> None:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    cells = notebook["cells"]
    joined_sources = "\n".join("".join(cell.get("source", [])) for cell in cells)

    assert "Environment setup and imports" in joined_sources
    assert "Process evidence intake for Codex-authored YAML" in joined_sources
    assert "build_process_intake_artifacts" in joined_sources
    assert "source_manifest.json" in joined_sources
    assert "process_research_brief.md" in joined_sources
    assert "codex_process_yaml_prompt.md" in joined_sources
    assert "Process library path configuration" in joined_sources
    assert "YAML schema / expected fields overview" in joined_sources
    assert "Discovery of all available process folders" in joined_sources
    assert "Shared helper functions" in joined_sources
    assert "YAML coherence analysis per discovered process" in joined_sources
    assert "Suggested YAML improvements per discovered process" in joined_sources
    assert "Gate 1: Aspen batch translator" in joined_sources
    assert "Gate 2: BKP COM load, extraction, and reports" in joined_sources
    assert "Gate 2 diagnostics and evidence bundle" in joined_sources
    assert "Codex session analysis per discovered process" in joined_sources
    assert "Output summary and validation" in joined_sources
    assert "analyze_process_spec_coherence" in joined_sources
    assert "apply_process_spec_improvements" in joined_sources
    assert "suggest_process_spec_improvements" in joined_sources
    assert "write_process_spec_file" in joined_sources
    assert "build_codex_spec_markdown" in joined_sources
    assert "build_codex_improvement_markdown" in joined_sources
    assert "build_codex_results_markdown" in joined_sources
    assert "load_result_artifact_tables" in joined_sources
    assert "B-SYN selectivity diagnostics" not in joined_sources
    assert "PURGE_SWEEP_FRACTIONS" not in joined_sources
    assert "run_methanol_tuning_campaign" not in joined_sources
    assert "MEOH-PRO" not in joined_sources
    assert "run_aspen_batch(" in joined_sources
    assert "run_process_batch_first(" in joined_sources
    assert joined_sources.index("run_aspen_batch(") < joined_sources.index("run_process_batch_first(")
    assert "run_process(" not in joined_sources
    assert "context_probe.json" in joined_sources
    assert "build_diagnostics.json" in joined_sources
    assert "simulation_diagnostics.json" in joined_sources
    assert "live_aspen_summary.json" in joined_sources
    assert "ENFORCE_ACCEPTANCE_TARGETS = False" in joined_sources
    assert "process_library" in joined_sources


def test_methanol_example_notebook_keeps_tuning_sections() -> None:
    notebook = json.loads(METHANOL_NOTEBOOK_PATH.read_text(encoding="utf-8"))
    joined_sources = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])

    assert "Methanol Example Runner: Kinetic Batch-First Aspen Workflow" in joined_sources
    assert 'ONLY_PROCESSES: set[str] | None = {"methanol"}' in joined_sources
    assert "Kinetic remediation and tuning worksheet" in joined_sources
    assert "Live methanol production tuning campaign" in joined_sources
    assert "B-SYN selectivity diagnostics" in joined_sources
    assert "recycle composition diagnostics" in joined_sources
    assert "PURGE_SWEEP_FRACTIONS" in joined_sources
    assert "ATR_TUNING_FACTORS" in joined_sources
    assert "run_methanol_tuning_campaign" in joined_sources
    assert "tuning_campaign_summary.csv" in joined_sources
    assert "best_process.yaml" in joined_sources
