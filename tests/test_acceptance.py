from __future__ import annotations

from typing import Any, Dict

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

    names = {check["name"] for check in acceptance["checks"]}
    assert "Production Rate" not in names
    assert acceptance["passed"] is True


def test_missing_purity_kpi() -> None:
    results = _base_results()
    results["kpis"]["purity_fraction"] = None
    acceptance = validate_acceptance(results, _base_spec())

    names = {check["name"] for check in acceptance["checks"]}
    assert "Methanol Purity" not in names
    assert acceptance["passed"] is True


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
