from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Union

from .parser import load_spec
from .serialization import spec_to_plain_dict
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
    return spec_to_plain_dict(spec)


def _stream_lookup(results: Dict[str, Any]) -> Dict[str, Mapping[str, Any]]:
    streams = results.get("streams") if isinstance(results, dict) else None
    if streams is None:
        return {}

    rows: List[Mapping[str, Any]] = []
    to_dict = getattr(streams, "to_dict", None)
    if callable(to_dict):
        try:
            records = to_dict(orient="records")
            if isinstance(records, list):
                rows = [row for row in records if isinstance(row, Mapping)]
        except TypeError:
            rows = []
    elif isinstance(streams, list):
        rows = [row for row in streams if isinstance(row, Mapping)]
    elif isinstance(streams, Mapping):
        rows = [streams]

    lookup: Dict[str, Mapping[str, Any]] = {}
    for row in rows:
        name = row.get("stream_name", row.get("name"))
        if name is None:
            continue
        lookup[str(name).upper()] = row
    return lookup


def _row_value(row: Mapping[str, Any], *names: str) -> Optional[float]:
    normalized = {str(key).lower(): value for key, value in row.items()}
    for name in names:
        value = normalized.get(name.lower())
        converted = _coerce_float(value)
        if converted is not None:
            return converted
    return None


def _component_mass_flow_kg_hr(row: Mapping[str, Any], component: str) -> Optional[float]:
    component_key = component.strip().upper()
    direct = _row_value(
        row,
        f"{component_key}_mass_flow_kg_hr",
        f"{component_key}_mass_flow",
        f"{component_key}_kg_hr",
    )
    if direct is not None:
        return direct

    mass_flow = _row_value(row, "mass_flow", "mass_flow_kg_hr")
    mass_fraction = _row_value(row, f"{component_key}_mass_frac", f"{component_key}_mass_fraction")
    if mass_flow is None or mass_fraction is None:
        return None
    return mass_flow * mass_fraction


def _kg_hr_to_tpd(value: float) -> float:
    return value * 24.0 / 1000.0


def _tpd_to_kg_hr(value: float) -> float:
    return value * 1000.0 / 24.0


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

    # Check 4: explicit product stream conditions, such as low-pressure methanol product.
    product_conditions = targets.get("product_conditions", [])
    if isinstance(product_conditions, list) and product_conditions:
        stream_rows = _stream_lookup(results)
        pressure_unit = str(
            spec_dict.get("metadata", {}).get("units", {}).get("pressure", "pressure units")
        )
        temperature_unit = str(
            spec_dict.get("metadata", {}).get("units", {}).get("temperature", "temperature units")
        )
        for index, condition in enumerate(product_conditions):
            if not isinstance(condition, Mapping):
                continue
            stream_name = str(condition.get("stream", "")).strip()
            row = stream_rows.get(stream_name.upper()) if stream_name else None
            pressure_target = _coerce_float(condition.get("pressure"))
            pressure_tolerance = _coerce_float(condition.get("pressure_tolerance"))
            pressure_tolerance = 0.05 if pressure_tolerance is None else pressure_tolerance
            temperature_target = _coerce_float(condition.get("temperature"))
            temperature_tolerance = _coerce_float(condition.get("temperature_tolerance"))
            temperature_tolerance = 1.0 if temperature_tolerance is None else temperature_tolerance

            if pressure_target is not None:
                actual_pressure = _row_value(row, "pressure", "pressure_bar", "pres") if row else None
                pressure_ok = (
                    actual_pressure is not None
                    and abs(actual_pressure - pressure_target) <= pressure_tolerance
                )
                checks.append(
                    {
                        "name": f"Product Condition: {stream_name} pressure",
                        "passed": pressure_ok,
                        "actual": "n/a" if actual_pressure is None else f"{actual_pressure:.4g} {pressure_unit}",
                        "expected": f"{pressure_target:.4g} {pressure_unit} +/- {pressure_tolerance:.4g}",
                        "message": (
                            "Within tolerance"
                            if pressure_ok
                            else f"Missing or outside pressure condition for {stream_name}"
                        ),
                    }
                )

            if temperature_target is not None:
                actual_temperature = _row_value(row, "temperature", "temperature_c", "temp") if row else None
                temperature_ok = (
                    actual_temperature is not None
                    and abs(actual_temperature - temperature_target) <= temperature_tolerance
                )
                checks.append(
                    {
                        "name": f"Product Condition: {stream_name} temperature",
                        "passed": temperature_ok,
                        "actual": "n/a" if actual_temperature is None else f"{actual_temperature:.4g} {temperature_unit}",
                        "expected": f"{temperature_target:.4g} {temperature_unit} +/- {temperature_tolerance:.4g}",
                        "message": (
                            "Within tolerance"
                            if temperature_ok
                            else f"Missing or outside temperature condition for {stream_name}"
                        ),
                    }
                )

    component_loss_checks: List[Dict[str, Any]] = []
    lights_recovery: Dict[str, Any] = {}
    component_loss_limits = targets.get("component_loss_limits", [])
    if isinstance(component_loss_limits, list) and component_loss_limits:
        stream_rows = _stream_lookup(results)
        for limit in component_loss_limits:
            if not isinstance(limit, Mapping):
                continue
            stream_name = str(limit.get("stream", "")).strip()
            component = str(limit.get("component", "")).strip()
            if not stream_name or not component:
                continue
            row = stream_rows.get(stream_name.upper())
            actual_kg_hr = _component_mass_flow_kg_hr(row, component) if row else None
            max_kg_hr = _coerce_float(limit.get("max_kg_hr"))
            max_tpd = _coerce_float(limit.get("max_tpd"))
            if max_kg_hr is None and max_tpd is not None:
                max_kg_hr = _tpd_to_kg_hr(max_tpd)
            if max_kg_hr is None:
                continue

            actual_tpd = None if actual_kg_hr is None else _kg_hr_to_tpd(actual_kg_hr)
            max_tpd_value = _kg_hr_to_tpd(max_kg_hr)
            loss_ok = actual_kg_hr is not None and actual_kg_hr <= max_kg_hr
            check = {
                "name": f"Component Loss: {stream_name} {component}",
                "passed": loss_ok,
                "actual": "n/a" if actual_kg_hr is None else f"{actual_kg_hr:.4g} kg/hr ({actual_tpd:.4g} TPD)",
                "expected": f"<={max_kg_hr:.4g} kg/hr ({max_tpd_value:.4g} TPD)",
                "message": "Within loss limit" if loss_ok else f"Missing or above component loss limit for {stream_name}/{component}",
                "stream": stream_name,
                "component": component,
                "actual_kg_hr": actual_kg_hr,
                "actual_tpd": actual_tpd,
                "limit_kg_hr": max_kg_hr,
                "limit_tpd": max_tpd_value,
            }

            baseline_kg_hr = _coerce_float(limit.get("baseline_kg_hr"))
            baseline_tpd = _coerce_float(limit.get("baseline_tpd"))
            if baseline_kg_hr is None and baseline_tpd is not None:
                baseline_kg_hr = _tpd_to_kg_hr(baseline_tpd)
            if baseline_kg_hr is not None and actual_kg_hr is not None:
                recovered_kg_hr = baseline_kg_hr - actual_kg_hr
                recovery_fraction = recovered_kg_hr / baseline_kg_hr if baseline_kg_hr > 0 else None
                check["baseline_kg_hr"] = baseline_kg_hr
                check["baseline_tpd"] = _kg_hr_to_tpd(baseline_kg_hr)
                check["recovered_kg_hr"] = recovered_kg_hr
                check["recovery_fraction"] = recovery_fraction

                if stream_name.upper() in {"VENT-GAS", "VENT-TOT"} and component.upper() == "CH3OH":
                    lights_recovery = {
                        "vent_stream": stream_name,
                        "vent_methanol_loss_kg_hr": actual_kg_hr,
                        "vent_methanol_loss_tpd": actual_tpd,
                        "baseline_lights_methanol_loss_kg_hr": baseline_kg_hr,
                        "baseline_lights_methanol_loss_tpd": _kg_hr_to_tpd(baseline_kg_hr),
                        "lights_methanol_recovered_kg_hr": recovered_kg_hr,
                        "lights_methanol_recovery_fraction": recovery_fraction,
                        "limit_kg_hr": max_kg_hr,
                        "limit_tpd": max_tpd_value,
                    }

            component_loss_checks.append(check)
            checks.append(check)

    return {
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
        "component_loss_checks": component_loss_checks,
        "lights_recovery": lights_recovery,
    }


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
