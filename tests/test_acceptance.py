from __future__ import annotations

from typing import Any, Dict

import pytest

from aspen_automation import validate_acceptance


def _base_spec() -> Dict[str, Any]:
    return {
        "targets": {
            "production_rate_tpd": 10000,
            "tolerance": 0.02,
            "purity": {
                "expression": "CH3OH wt% in MEOH-PRO",
                "min_value": 0.9985,
            },
        }
    }


def _base_results() -> Dict[str, Any]:
    return {
        "kpis": {
            "convergence_status": "converged",
            "production_rate_tpd": 10000.0,
            "purity_fraction": 0.9987,
        }
    }


def _check_by_name(acceptance: Dict[str, Any], name: str) -> Dict[str, Any]:
    return next(check for check in acceptance["checks"] if check["name"] == name)


def test_all_pass_converged() -> None:
    acceptance = validate_acceptance(_base_results(), _base_spec())
    assert acceptance["passed"] is True
    assert {check["name"] for check in acceptance["checks"]} == {
        "Convergence",
        "Production Rate",
        "Methanol Purity",
    }


def test_fail_not_converged() -> None:
    results = _base_results()
    results["kpis"]["convergence_status"] = "failed"
    acceptance = validate_acceptance(results, _base_spec())

    assert acceptance["passed"] is False
    assert _check_by_name(acceptance, "Convergence")["passed"] is False


def test_pass_convergence_case_insensitive() -> None:
    results = _base_results()
    results["kpis"]["convergence_status"] = "Converged"
    acceptance = validate_acceptance(results, _base_spec())

    assert acceptance["passed"] is True
    assert _check_by_name(acceptance, "Convergence")["passed"] is True


def test_fail_production_below_tolerance() -> None:
    results = _base_results()
    results["kpis"]["production_rate_tpd"] = 9799.9
    acceptance = validate_acceptance(results, _base_spec())

    assert acceptance["passed"] is False
    assert _check_by_name(acceptance, "Production Rate")["passed"] is False


def test_fail_production_above_tolerance() -> None:
    results = _base_results()
    results["kpis"]["production_rate_tpd"] = 10200.1
    acceptance = validate_acceptance(results, _base_spec())

    assert acceptance["passed"] is False
    assert _check_by_name(acceptance, "Production Rate")["passed"] is False


def test_fail_purity_below_min() -> None:
    results = _base_results()
    results["kpis"]["purity_fraction"] = 0.9984
    acceptance = validate_acceptance(results, _base_spec())

    assert acceptance["passed"] is False
    assert _check_by_name(acceptance, "Methanol Purity")["passed"] is False


def test_pass_purity_at_boundary() -> None:
    results = _base_results()
    results["kpis"]["purity_fraction"] = 0.9985
    acceptance = validate_acceptance(results, _base_spec())

    assert acceptance["passed"] is True
    assert _check_by_name(acceptance, "Methanol Purity")["passed"] is True


def test_pass_production_at_lower_boundary() -> None:
    results = _base_results()
    results["kpis"]["production_rate_tpd"] = 9800.0
    acceptance = validate_acceptance(results, _base_spec())

    assert acceptance["passed"] is True
    assert _check_by_name(acceptance, "Production Rate")["passed"] is True


def test_pass_production_at_upper_boundary() -> None:
    results = _base_results()
    results["kpis"]["production_rate_tpd"] = 10200.0
    acceptance = validate_acceptance(results, _base_spec())

    assert acceptance["passed"] is True
    assert _check_by_name(acceptance, "Production Rate")["passed"] is True


def test_missing_production_kpi() -> None:
    results = _base_results()
    results["kpis"]["production_rate_tpd"] = None
    acceptance = validate_acceptance(results, _base_spec())

    production_check = _check_by_name(acceptance, "Production Rate")
    assert production_check["passed"] is False
    assert production_check["message"] == "Missing KPI production_rate_tpd"
    assert acceptance["passed"] is False


def test_missing_purity_kpi() -> None:
    results = _base_results()
    results["kpis"]["purity_fraction"] = None
    acceptance = validate_acceptance(results, _base_spec())

    purity_check = _check_by_name(acceptance, "Methanol Purity")
    assert purity_check["passed"] is False
    assert purity_check["message"] == "Missing KPI purity_fraction"
    assert acceptance["passed"] is False


def test_no_targets_in_spec() -> None:
    acceptance = validate_acceptance(_base_results(), {})
    assert acceptance["passed"] is True
    assert len(acceptance["checks"]) == 1
    assert acceptance["checks"][0]["name"] == "Convergence"


def test_checks_structure() -> None:
    acceptance = validate_acceptance(_base_results(), _base_spec())
    required_keys = {"name", "passed", "actual", "expected", "message"}

    for check in acceptance["checks"]:
        assert required_keys.issubset(check.keys())


def test_purity_legacy_min_key_supported() -> None:
    spec = {
        "targets": {
            "production_rate_tpd": 10000,
            "tolerance": 0.02,
            "purity": {
                "expression": "CH3OH wt% in MEOH-PRO",
                "min": 0.9985,
            },
        }
    }
    acceptance = validate_acceptance(_base_results(), spec)

    assert acceptance["passed"] is True
    assert _check_by_name(acceptance, "Methanol Purity")["passed"] is True


def test_product_pressure_condition_passes_at_low_pressure_target() -> None:
    spec = _base_spec()
    spec["metadata"] = {"units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}}
    spec["targets"]["product_conditions"] = [
        {"stream": "MEOH-PRO", "pressure": 1.5, "pressure_tolerance": 0.05}
    ]
    results = _base_results()
    results["streams"] = [{"stream_name": "MEOH-PRO", "pressure": 1.52}]

    acceptance = validate_acceptance(results, spec)

    check = _check_by_name(acceptance, "Product Condition: MEOH-PRO pressure")
    assert check["passed"] is True
    assert acceptance["passed"] is True


def test_product_pressure_condition_fails_at_80_bar() -> None:
    spec = _base_spec()
    spec["metadata"] = {"units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}}
    spec["targets"]["product_conditions"] = [
        {"stream": "MEOH-PRO", "pressure": 1.5, "pressure_tolerance": 0.05}
    ]
    results = _base_results()
    results["streams"] = [{"stream_name": "MEOH-PRO", "pressure": 80.0}]

    acceptance = validate_acceptance(results, spec)

    check = _check_by_name(acceptance, "Product Condition: MEOH-PRO pressure")
    assert check["passed"] is False
    assert acceptance["passed"] is False


def test_product_pressure_condition_fails_when_stream_missing() -> None:
    spec = _base_spec()
    spec["targets"]["product_conditions"] = [
        {"stream": "MEOH-PRO", "pressure": 1.5, "pressure_tolerance": 0.05}
    ]
    results = _base_results()
    results["streams"] = [{"stream_name": "WASTE-H2O", "pressure": 2.08}]

    acceptance = validate_acceptance(results, spec)

    check = _check_by_name(acceptance, "Product Condition: MEOH-PRO pressure")
    assert check["passed"] is False
    assert check["actual"] == "n/a"


def test_component_loss_limit_passes_and_reports_lights_recovery() -> None:
    spec = _base_spec()
    spec["targets"]["component_loss_limits"] = [
        {
            "stream": "VENT-GAS",
            "component": "CH3OH",
            "max_kg_hr": 26200.0,
            "baseline_kg_hr": 261131.0,
            "basis": "mass",
        }
    ]
    results = _base_results()
    results["streams"] = [
        {"stream_name": "VENT-GAS", "mass_flow": 75000.0, "CH3OH_mass_frac": 0.30}
    ]

    acceptance = validate_acceptance(results, spec)

    check = _check_by_name(acceptance, "Component Loss: VENT-GAS CH3OH")
    assert check["passed"] is True
    assert check["actual_kg_hr"] == 22500.0
    assert acceptance["lights_recovery"]["vent_methanol_loss_tpd"] == 540.0
    assert acceptance["lights_recovery"]["lights_methanol_recovery_fraction"] > 0.91
    assert acceptance["passed"] is True


def test_component_loss_limit_reports_combined_vent_lights_recovery() -> None:
    spec = _base_spec()
    spec["targets"]["component_loss_limits"] = [
        {
            "stream": "VENT-TOT",
            "component": "CH3OH",
            "max_kg_hr": 26200.0,
            "baseline_kg_hr": 261131.0,
        }
    ]
    results = _base_results()
    results["streams"] = [
        {"stream_name": "VENT-TOT", "mass_flow": 64060.0, "CH3OH_mass_frac": 0.38}
    ]

    acceptance = validate_acceptance(results, spec)

    check = _check_by_name(acceptance, "Component Loss: VENT-TOT CH3OH")
    assert check["passed"] is True
    assert check["actual_kg_hr"] == pytest.approx(24342.8)
    assert acceptance["lights_recovery"]["vent_stream"] == "VENT-TOT"
    assert acceptance["lights_recovery"]["vent_methanol_loss_tpd"] == pytest.approx(584.2272)
    assert acceptance["passed"] is True


def test_component_loss_limit_fails_when_vent_methanol_is_too_high() -> None:
    spec = _base_spec()
    spec["targets"]["component_loss_limits"] = [
        {"stream": "VENT-GAS", "component": "CH3OH", "max_tpd": 627.0}
    ]
    results = _base_results()
    results["streams"] = [
        {"stream_name": "VENT-GAS", "mass_flow": 75000.0, "CH3OH_mass_frac": 0.40}
    ]

    acceptance = validate_acceptance(results, spec)

    check = _check_by_name(acceptance, "Component Loss: VENT-GAS CH3OH")
    assert check["passed"] is False
    assert check["actual_tpd"] == 720.0
    assert acceptance["passed"] is False


def test_component_loss_limit_fails_when_stream_is_missing() -> None:
    spec = _base_spec()
    spec["targets"]["component_loss_limits"] = [
        {"stream": "VENT-GAS", "component": "CH3OH", "max_kg_hr": 26200.0}
    ]
    results = _base_results()
    results["streams"] = [{"stream_name": "MEOH-PRO", "mass_flow": 1.0, "CH3OH_mass_frac": 1.0}]

    acceptance = validate_acceptance(results, spec)

    check = _check_by_name(acceptance, "Component Loss: VENT-GAS CH3OH")
    assert check["passed"] is False
    assert check["actual"] == "n/a"
    assert acceptance["passed"] is False
