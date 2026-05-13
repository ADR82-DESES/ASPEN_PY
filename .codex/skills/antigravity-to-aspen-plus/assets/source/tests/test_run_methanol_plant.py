from __future__ import annotations

import builtins
import os
import runpy
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, mock_open, patch

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "run_methanol_plant.py"
if str(SCRIPT_PATH.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_PATH.parent))

from aspen_automation.exceptions import BuildError, ExtractionError, ValidationError


BASE_DIR = SCRIPT_PATH.parent
YAML_PATH = os.path.normpath(str(BASE_DIR / "templates" / "methanol_plant_atr.yaml"))
PLANT_DIR = os.path.normpath(str(BASE_DIR / "Methanol Plant"))
GENERATED_INP_PATH = os.path.normpath(str(BASE_DIR / "Methanol Plant" / "MethanolPlant_generated.inp"))
OUTPUT_APW_PATH = os.path.normpath(str(BASE_DIR / "Methanol Plant" / "MethanolPlant_output.apw"))
RESULTS_DIR = os.path.normpath(str(BASE_DIR / "Methanol Plant" / "results"))
SESSION_TEMP_DIR = os.path.normpath(str(BASE_DIR / "Methanol_Session"))

_UNSET = object()


@dataclass
class ScriptRun:
    exit_code: int
    stdout: str
    aspen: MagicMock | None
    spec: dict[str, Any]
    extracted_results: dict[str, Any]
    mock_load_spec: MagicMock
    mock_generate_inp: MagicMock
    mock_run_session: MagicMock
    mock_extract_results: MagicMock
    mock_cleanup_session: MagicMock
    mock_makedirs: MagicMock
    mock_json_dump: MagicMock
    mock_open_handle: MagicMock


def _make_session_result(status: str, aspen: MagicMock | None) -> SimpleNamespace:
    return SimpleNamespace(
        build_mode="auto",
        build_mechanism_used="InitFromFile2",
        build_fallback_attempted=False,
        diagnostics={},
        convergence_status=status,
        simulation_time_seconds=12.5,
        aspen=aspen,
    )


def _make_extraction_result() -> dict[str, Any]:
    streams_df = MagicMock(name="streams_df")
    blocks_df = MagicMock(name="blocks_df")
    return {
        "streams": streams_df,
        "blocks": blocks_df,
        "kpis": {"production_rate_tpd": 10000.0},
    }


def _run_script(
    capsys,
    *,
    status: str = "converged",
    aspen: MagicMock | None | object = _UNSET,
    load_spec_side_effect: Exception | None = None,
    generate_inp_side_effect: Exception | None = None,
    run_session_side_effect: Exception | None = None,
    extract_results_side_effect: Exception | None = None,
    save_as_side_effect: Exception | None = None,
) -> ScriptRun:
    if aspen is _UNSET:
        aspen = MagicMock(name="aspen")

    assert aspen is _UNSET or aspen is None or isinstance(aspen, MagicMock)
    if isinstance(aspen, MagicMock) and save_as_side_effect is not None:
        aspen.SaveAs.side_effect = save_as_side_effect

    spec = {"metadata": {"title": "Orchestration test"}}
    extracted_results = _make_extraction_result()
    session_result = _make_session_result(status=status, aspen=aspen if aspen is not _UNSET else None)

    real_open = builtins.open
    write_open = mock_open()

    def _open_side_effect(file, mode="r", *args, **kwargs):
        if "w" in mode:
            return write_open(file, mode, *args, **kwargs)
        return real_open(file, mode, *args, **kwargs)

    with (
        patch("aspen_automation.load_spec", return_value=spec) as mock_load_spec,
        patch("aspen_automation.generate_inp") as mock_generate_inp,
        patch("aspen_automation.run_simulation_session", return_value=session_result) as mock_run_session,
        patch("aspen_automation.extract_results", return_value=extracted_results) as mock_extract_results,
        patch("aspen_automation.session._cleanup_session") as mock_cleanup_session,
        patch("os.makedirs") as mock_makedirs,
        patch("json.dump") as mock_json_dump,
        patch("builtins.open", side_effect=_open_side_effect) as mock_open_handle,
    ):
        if load_spec_side_effect is not None:
            mock_load_spec.side_effect = load_spec_side_effect
        if generate_inp_side_effect is not None:
            mock_generate_inp.side_effect = generate_inp_side_effect
        if run_session_side_effect is not None:
            mock_run_session.side_effect = run_session_side_effect
        if extract_results_side_effect is not None:
            mock_extract_results.side_effect = extract_results_side_effect

        try:
            runpy.run_path(str(SCRIPT_PATH), run_name="__main__")
            exit_code = 0
        except SystemExit as exc:
            exit_code = exc.code

    stdout = capsys.readouterr().out
    return ScriptRun(
        exit_code=exit_code,
        stdout=stdout,
        aspen=aspen if aspen is not _UNSET else None,
        spec=spec,
        extracted_results=extracted_results,
        mock_load_spec=mock_load_spec,
        mock_generate_inp=mock_generate_inp,
        mock_run_session=mock_run_session,
        mock_extract_results=mock_extract_results,
        mock_cleanup_session=mock_cleanup_session,
        mock_makedirs=mock_makedirs,
        mock_json_dump=mock_json_dump,
        mock_open_handle=mock_open_handle,
    )


def test_main_success_orchestrates_flow(capsys) -> None:
    run = _run_script(capsys)

    assert run.exit_code == 0
    run.mock_load_spec.assert_called_once_with(YAML_PATH)
    run.mock_generate_inp.assert_called_once_with(run.spec, output_path=GENERATED_INP_PATH)
    run.mock_run_session.assert_called_once_with(
        run.spec,
        build_mode="auto",
        output_dir=SESSION_TEMP_DIR,
        keep_alive=True,
        timeout_seconds=1800,
        visible=True,
    )
    assert isinstance(run.aspen, MagicMock)
    run.aspen.SaveAs.assert_called_once_with(OUTPUT_APW_PATH)
    run.mock_extract_results.assert_called_once_with(run.aspen, run.spec)
    run.extracted_results["streams"].to_csv.assert_called_once_with(
        os.path.join(RESULTS_DIR, "streams.csv"),
        index=False,
    )
    run.extracted_results["blocks"].to_csv.assert_called_once_with(
        os.path.join(RESULTS_DIR, "blocks.csv"),
        index=False,
    )
    run.mock_json_dump.assert_called_once()
    run.mock_cleanup_session.assert_not_called()
    assert "Clean-up disabled for inspection" in run.stdout


def test_main_timeout_status_returns_5_and_skips_save(capsys) -> None:
    run = _run_script(capsys, status="timeout")

    assert run.exit_code == 5
    assert isinstance(run.aspen, MagicMock)
    run.aspen.SaveAs.assert_not_called()
    run.mock_extract_results.assert_not_called()
    run.mock_cleanup_session.assert_not_called()
    assert "Clean-up disabled for inspection" in run.stdout


def test_main_failed_status_returns_non_zero_and_does_not_save(capsys) -> None:
    run = _run_script(capsys, status="failed")

    assert run.exit_code == 3
    assert isinstance(run.aspen, MagicMock)
    run.aspen.SaveAs.assert_not_called()
    run.mock_extract_results.assert_not_called()
    run.mock_cleanup_session.assert_not_called()
    assert "Clean-up disabled for inspection" in run.stdout


def test_main_unknown_status_returns_non_zero_and_does_not_save(capsys) -> None:
    run = _run_script(capsys, status="unknown")

    assert run.exit_code == 3
    assert isinstance(run.aspen, MagicMock)
    run.aspen.SaveAs.assert_not_called()
    run.mock_extract_results.assert_not_called()
    run.mock_cleanup_session.assert_not_called()
    assert "Clean-up disabled for inspection" in run.stdout


def test_main_unrecognized_status_returns_non_zero_and_does_not_save(capsys) -> None:
    run = _run_script(capsys, status="partial")

    assert run.exit_code == 3
    assert isinstance(run.aspen, MagicMock)
    run.aspen.SaveAs.assert_not_called()
    run.mock_extract_results.assert_not_called()
    run.mock_cleanup_session.assert_not_called()
    assert "Clean-up disabled for inspection" in run.stdout


def test_main_save_failure_returns_2(capsys) -> None:
    run = _run_script(capsys, save_as_side_effect=OSError("disk full"))

    assert run.exit_code == 2
    assert isinstance(run.aspen, MagicMock)
    run.aspen.SaveAs.assert_called_once_with(OUTPUT_APW_PATH)
    run.mock_extract_results.assert_not_called()
    run.mock_cleanup_session.assert_not_called()
    assert "Clean-up disabled for inspection" in run.stdout


def test_main_extraction_error_returns_zero_after_save(capsys) -> None:
    run = _run_script(capsys, extract_results_side_effect=ExtractionError("extract failed"))

    assert run.exit_code == 0
    assert isinstance(run.aspen, MagicMock)
    run.aspen.SaveAs.assert_called_once_with(OUTPUT_APW_PATH)
    run.mock_extract_results.assert_called_once_with(run.aspen, run.spec)
    run.mock_cleanup_session.assert_not_called()
    assert "Clean-up disabled for inspection" in run.stdout


def test_main_validation_error_returns_1(capsys) -> None:
    run = _run_script(
        capsys,
        load_spec_side_effect=ValidationError("invalid spec", report={"errors": ["invalid"]}),
    )

    assert run.exit_code == 1
    run.mock_generate_inp.assert_not_called()
    run.mock_run_session.assert_not_called()
    run.mock_cleanup_session.assert_not_called()


def test_main_build_error_returns_3(capsys) -> None:
    run = _run_script(capsys, run_session_side_effect=BuildError("build failed"))

    assert run.exit_code == 3
    run.mock_extract_results.assert_not_called()
    run.mock_cleanup_session.assert_not_called()


def test_main_unexpected_error_returns_1(capsys) -> None:
    run = _run_script(capsys, run_session_side_effect=RuntimeError("unexpected"))

    assert run.exit_code == 1
    run.mock_extract_results.assert_not_called()
    run.mock_cleanup_session.assert_not_called()


def test_main_missing_aspen_returns_1_and_skips_cleanup(capsys) -> None:
    run = _run_script(capsys, aspen=None, status="converged")

    assert run.exit_code == 1
    run.mock_extract_results.assert_not_called()
    run.mock_cleanup_session.assert_not_called()
