from __future__ import annotations

import datetime as _dt
import os
from typing import Any, Dict, Mapping, Union

import pandas as pd

from .acceptance import validate_acceptance
from .extractor import ENERGY_BALANCE_VIEW_LEGACY, extract_results
from .parser import load_spec
from .reporter import generate_reports
from .schema import PlantSpecification
from .session import SessionResult, _cleanup_session, run_simulation_session
from .validator import validate_spec

SpecInput = Union[str, PlantSpecification, Mapping[str, Any]]


def _normalize_spec(spec: SpecInput) -> PlantSpecification:
    if isinstance(spec, PlantSpecification):
        report = validate_spec(spec.model_dump())
        if not report["valid"]:
            raise ValueError(f"Invalid PlantSpecification: {report['errors']}")
        return spec

    if isinstance(spec, str):
        loaded = load_spec(spec)
        return PlantSpecification(**loaded)

    if isinstance(spec, Mapping):
        spec_dict = dict(spec)
        report = validate_spec(spec_dict)
        if not report["valid"]:
            raise ValueError(f"Invalid spec dict: {report['errors']}")
        return PlantSpecification(**spec_dict)

    raise TypeError(
        f"spec must be a PlantSpecification, mapping, or file path str; got {type(spec).__name__}"
    )


def _session_to_dict(result: SessionResult) -> Dict[str, Any]:
    return {
        "build_mode": result.build_mode,
        "build_mechanism_used": result.build_mechanism_used,
        "build_fallback_attempted": result.build_fallback_attempted,
        "convergence_status": result.convergence_status,
        "simulation_time_seconds": result.simulation_time_seconds,
        "diagnostics": dict(result.diagnostics),
    }


def _empty_results(session_result: SessionResult) -> Dict[str, Any]:
    return {
        "streams": pd.DataFrame(),
        "blocks": pd.DataFrame(),
        "material_balance": pd.DataFrame(),
        "energy_balance": pd.DataFrame(),
        "kpis": {
            "production_rate_tpd": None,
            "purity_fraction": None,
            "energy_consumption_mw": None,
            "yield_fraction": None,
            "convergence_status": session_result.convergence_status,
        },
        "diagnostics": dict(session_result.diagnostics),
        "metadata": {
            "extracted_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "stream_count": 0,
            "block_count": 0,
            "component_count": 0,
        },
    }


def run_simulation(
    spec: SpecInput,
    build_mode: str = "auto",
    output_dir: str = "results/",
    visible: bool = True,
    timeout_seconds: int = 300,
    keep_alive: bool = False,
    report_format: str = "html",
    energy_balance_view: str = ENERGY_BALANCE_VIEW_LEGACY,
    raise_on_connection_error: bool = False,
) -> Dict[str, Any]:
    """
    Run the end-to-end Aspen automation pipeline.

    This orchestrates:
    spec load/validation -> build/run session -> extraction -> reporting -> acceptance.
    """
    normalized_spec = _normalize_spec(spec)
    session_result = run_simulation_session(
        normalized_spec,
        build_mode=build_mode,
        output_dir=output_dir,
        visible=visible,
        timeout_seconds=timeout_seconds,
        keep_alive=True,
        raise_on_connection_error=raise_on_connection_error,
    )

    aspen = session_result.aspen
    try:
        if aspen is None:
            results = _empty_results(session_result)
        else:
            results = extract_results(aspen, normalized_spec, energy_balance_view=energy_balance_view)

        kpis = results.get("kpis")
        if not isinstance(kpis, dict):
            kpis = {}
            results["kpis"] = kpis
        kpis["convergence_status"] = session_result.convergence_status
        kpis["simulation_time_seconds"] = session_result.simulation_time_seconds

        report_dir = generate_reports(results, normalized_spec, output_dir=output_dir, format=report_format)
        acceptance = validate_acceptance(results, normalized_spec)

        results["acceptance"] = acceptance
        results["report_dir"] = report_dir
        results["session"] = _session_to_dict(session_result)
        return results
    finally:
        if aspen is not None:
            _cleanup_session(
                aspen,
                output_dir=output_dir,
                inp_path=os.path.join(output_dir, "temp_simulation.inp"),
                keep_alive=keep_alive,
            )

