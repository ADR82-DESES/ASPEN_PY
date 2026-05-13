from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from aspen_automation.runner import run_simulation
from aspen_automation.schema import PlantSpecification
from aspen_automation.session import SessionResult


def _spec_dict() -> dict:
    return {
        "metadata": {
            "title": "Runner Test Plant",
            "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"},
        },
        "components": [{"id": "CH3OH", "name": "METHANOL"}],
        "properties": {"method": "RK-SOAVE"},
        "flowsheet": [{"block": "B1", "inputs": ["FEED"], "outputs": ["MEOH-PRO"]}],
        "streams": [
            {
                "name": "FEED",
                "temperature": 25,
                "pressure": 1,
                "mass_flow": 1000,
                "composition": {"CH3OH": 1.0},
            }
        ],
        "blocks": [{"name": "B1", "type": "MIXER"}],
        "targets": {
            "production_rate_tpd": 10000,
            "tolerance": 0.02,
            "purity": {"expression": "CH3OH wt% in MEOH-PRO", "min_value": 0.9985},
        },
    }


def _extracted_results() -> dict:
    return {
        "streams": pd.DataFrame(
            [{"stream_name": "MEOH-PRO", "mass_flow": 416666.7, "CH3OH_mass_frac": 0.999}]
        ),
        "blocks": pd.DataFrame([{"block_name": "B1", "duty_kw": 0.0}]),
        "material_balance": pd.DataFrame([{"component": "CH3OH", "closure_pct": 0.0}]),
        "energy_balance": pd.DataFrame([{"block_name": "TOTAL", "duty_kw": 0.0}]),
        "kpis": {
            "production_rate_tpd": 10000.0,
            "purity_fraction": 0.999,
            "convergence_status": "unknown",
        },
        "diagnostics": {"convergence_status": "converged"},
        "metadata": {"stream_count": 1, "block_count": 1, "component_count": 1},
    }


def _session_result(aspen: object | None = None, status: str = "converged") -> SessionResult:
    return SessionResult(
        convergence_status=status,
        build_mode="auto",
        build_mechanism_used="InitFromFile2",
        build_fallback_attempted=False,
        simulation_time_seconds=12.5,
        diagnostics={"build_mechanism": "InitFromFile2"},
        aspen=aspen,
    )


def test_run_simulation_orchestrates_pipeline() -> None:
    with (
        patch(
            "aspen_automation.runner.run_simulation_session",
            return_value=_session_result(aspen=MagicMock(), status="converged"),
        ) as mock_session,
        patch("aspen_automation.runner.extract_results", return_value=_extracted_results()) as mock_extract,
        patch("aspen_automation.runner.generate_reports", return_value="results/run_123") as mock_reports,
        patch("aspen_automation.runner._cleanup_session") as mock_cleanup,
    ):
        result = run_simulation(_spec_dict(), output_dir="results", visible=False)

    mock_session.assert_called_once()
    mock_extract.assert_called_once()
    mock_reports.assert_called_once()
    mock_cleanup.assert_called_once()

    assert result["kpis"]["convergence_status"] == "converged"
    assert result["report_dir"] == "results/run_123"
    assert result["acceptance"]["passed"] is True
    assert result["session"]["build_mechanism_used"] == "InitFromFile2"


def test_run_simulation_respects_keep_alive() -> None:
    with (
        patch(
            "aspen_automation.runner.run_simulation_session",
            return_value=_session_result(aspen=MagicMock(), status="converged"),
        ),
        patch("aspen_automation.runner.extract_results", return_value=_extracted_results()),
        patch("aspen_automation.runner.generate_reports", return_value="results/run_123"),
        patch("aspen_automation.runner._cleanup_session") as mock_cleanup,
    ):
        run_simulation(_spec_dict(), output_dir="results", keep_alive=True)

    assert mock_cleanup.call_args.kwargs["keep_alive"] is True


def test_run_simulation_handles_missing_aspen_and_still_reports() -> None:
    failed_result = _session_result(aspen=None, status="failed")
    failed_result.diagnostics["error"] = "Cannot connect"

    with (
        patch("aspen_automation.runner.run_simulation_session", return_value=failed_result),
        patch("aspen_automation.runner.extract_results") as mock_extract,
        patch("aspen_automation.runner.generate_reports", return_value="results/run_failed"),
        patch("aspen_automation.runner._cleanup_session") as mock_cleanup,
    ):
        result = run_simulation(_spec_dict(), output_dir="results")

    mock_extract.assert_not_called()
    mock_cleanup.assert_not_called()
    assert isinstance(result["streams"], pd.DataFrame)
    assert result["kpis"]["convergence_status"] == "failed"
    assert result["report_dir"] == "results/run_failed"
    assert result["acceptance"]["passed"] is False


def test_run_simulation_loads_spec_from_path() -> None:
    with (
        patch("aspen_automation.runner.load_spec", return_value=_spec_dict()) as mock_load_spec,
        patch(
            "aspen_automation.runner.run_simulation_session",
            return_value=_session_result(aspen=None, status="failed"),
        ) as mock_session,
        patch("aspen_automation.runner.generate_reports", return_value="results/run_from_path"),
    ):
        run_simulation("templates/methanol_plant_atr.yaml", output_dir="results")

    mock_load_spec.assert_called_once_with("templates/methanol_plant_atr.yaml")
    normalized_spec = mock_session.call_args.args[0]
    assert isinstance(normalized_spec, PlantSpecification)


def test_run_simulation_rejects_invalid_spec_dict() -> None:
    with pytest.raises(ValueError, match="Invalid spec dict"):
        run_simulation({"metadata": {}}, output_dir="results")
