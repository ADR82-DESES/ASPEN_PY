from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Union

from .parser import load_spec
from .schema import PlantSpecification


Check = Dict[str, Any]
SpecInput = Union[PlantSpecification, Mapping[str, Any]]


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _spec_to_dict(spec: SpecInput) -> Dict[str, Any]:
    if isinstance(spec, PlantSpecification):
        return spec.model_dump()
    if isinstance(spec, Mapping):
        return dict(spec)
    raise TypeError(f"spec must be PlantSpecification or mapping; got {type(spec).__name__}")


def validate_acceptance(results: Dict[str, Any], spec: SpecInput) -> Dict[str, Any]:
    """
    Validate simulation results against acceptance criteria from spec targets.

    Returns:
        {
            "passed": bool,
            "checks": [{"name", "passed", "actual", "expected", "message"}, ...]
        }
    """
    checks: List[Check] = []

    kpis = results.get("kpis", {}) if isinstance(results, dict) else {}
    raw_status = kpis.get("convergence_status", "unknown")
    convergence_status = str(raw_status).strip() if raw_status is not None else "unknown"
    converged = convergence_status.lower() == "converged"
    checks.append(
        {
            "name": "Convergence",
            "passed": converged,
            "actual": convergence_status,
            "expected": "converged",
            "message": "Converged" if converged else "Simulation did not converge",
        }
    )

    spec_dict = _spec_to_dict(spec)
    targets = spec_dict.get("targets", {})
    targets = targets if isinstance(targets, dict) else {}

    # Check 2: Production rate against target +/- tolerance.
    target_tpd = _coerce_float(targets.get("production_rate_tpd"))
    tolerance = _coerce_float(targets.get("tolerance"))
    tolerance = 0.02 if tolerance is None else tolerance
    actual_tpd = _coerce_float(kpis.get("production_rate_tpd"))

    if target_tpd is not None:
        if actual_tpd is None:
            checks.append(
                {
                    "name": "Production Rate",
                    "passed": False,
                    "actual": "n/a",
                    "expected": f"{target_tpd:.0f} TPD +/- {tolerance*100:.1f}%",
                    "message": "Missing KPI production_rate_tpd",
                }
            )
        else:
            lower_bound = target_tpd * (1.0 - tolerance)
            upper_bound = target_tpd * (1.0 + tolerance)
            production_ok = lower_bound <= actual_tpd <= upper_bound
            checks.append(
                {
                    "name": "Production Rate",
                    "passed": production_ok,
                    "actual": f"{actual_tpd:.1f} TPD",
                    "expected": f"{target_tpd:.0f} TPD +/- {tolerance*100:.1f}%",
                    "message": "Within tolerance" if production_ok else "Outside tolerance",
                }
            )

    # Check 3: Product purity against minimum.
    purity_cfg = targets.get("purity", {})
    purity_cfg = purity_cfg if isinstance(purity_cfg, dict) else {}
    # Accept both schema field (min_value) and legacy field (min).
    min_purity = _coerce_float(purity_cfg.get("min_value"))
    if min_purity is None:
        min_purity = _coerce_float(purity_cfg.get("min"))
    actual_purity = _coerce_float(kpis.get("purity_fraction"))

    if min_purity is not None:
        if actual_purity is None:
            checks.append(
                {
                    "name": "Methanol Purity",
                    "passed": False,
                    "actual": "n/a",
                    "expected": f">={min_purity*100:.2f}%",
                    "message": "Missing KPI purity_fraction",
                }
            )
        else:
            purity_ok = actual_purity >= min_purity
            checks.append(
                {
                    "name": "Methanol Purity",
                    "passed": purity_ok,
                    "actual": f"{actual_purity*100:.2f}%",
                    "expected": f">={min_purity*100:.2f}%",
                    "message": "Meets specification" if purity_ok else "Below specification",
                }
            )

    return {"passed": all(check["passed"] for check in checks), "checks": checks}


def print_acceptance_report(acceptance: Dict[str, Any], spec_path: str = "") -> None:
    """Print a formatted acceptance report to stdout."""
    checks = acceptance.get("checks", [])
    passed = bool(acceptance.get("passed", False))

    print("=" * 80)
    print("Acceptance Validation Report")
    print("=" * 80)
    if spec_path:
        print(f"Specification: {spec_path}")
    print(f"Run: {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    overall = "PASSED" if passed else "FAILED"
    print(f"\nOverall Status: {overall}\n")

    print("Checks:")
    for check in checks:
        mark = "[PASS]" if check.get("passed") else "[FAIL]"
        print(f"  {mark} {check.get('name', 'Unnamed Check')}")
        print(f"    Expected: {check.get('expected', 'n/a')}")
        print(f"    Actual:   {check.get('actual', 'n/a')}")
        message = check.get("message")
        if message:
            print(f"    Detail:   {message}")
        print("")

    if passed:
        print("All acceptance criteria met.")
    else:
        failed_checks = [str(c.get("name")) for c in checks if not c.get("passed")]
        if failed_checks:
            print(f"Failed checks: {', '.join(failed_checks)}")
        else:
            print("Acceptance failed.")
    print("=" * 80)


def load_template(name: str = "methanol_plant_atr") -> Dict[str, Any]:
    """Load a template spec by name from the repository-level templates directory."""
    package_dir = Path(__file__).resolve().parent
    template_path = (package_dir.parent / "templates" / f"{name}.yaml").resolve()
    return load_spec(str(template_path))


__all__ = ["validate_acceptance", "print_acceptance_report", "load_template"]
