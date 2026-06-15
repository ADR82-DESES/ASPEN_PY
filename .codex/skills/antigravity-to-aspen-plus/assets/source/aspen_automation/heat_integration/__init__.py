"""Heat-integration pinch analysis (post-processing on converged run artifacts)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from .config import HeatIntegrationConfig, SteamLevel
from .energy_kpi import build_energy_kpi
from .pinch import PinchResult, build_composite_curves, pinch_analysis
from .thermal_streams import ThermalStream, extract_thermal_streams
from .utility_targeting import UtilityTarget, target_utilities

__all__ = [
    "HeatIntegrationConfig",
    "SteamLevel",
    "ThermalStream",
    "PinchResult",
    "UtilityTarget",
    "pinch_analysis",
    "build_composite_curves",
    "extract_thermal_streams",
    "target_utilities",
    "build_energy_kpi",
    "analyze_heat_integration",
    "figures_for_run",
]


def _compressor_work_mw(blocks_df: pd.DataFrame) -> float:
    if "block_type" not in blocks_df.columns or "net_work_mw" not in blocks_df.columns:
        return 0.0
    mask = blocks_df["block_type"].astype(str).str.upper() == "COMPR"
    vals = pd.to_numeric(blocks_df.loc[mask, "net_work_mw"], errors="coerce").dropna()
    return float(vals.sum())


def analyze_heat_integration(
    blocks_df: pd.DataFrame,
    streams_df: pd.DataFrame,
    spec_dict: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Run the full pinch chain; return the energy-KPI dict, or ``None`` if no streams."""
    config = HeatIntegrationConfig.from_spec(spec_dict)
    flowsheet = (spec_dict or {}).get("flowsheet") or []
    streams = extract_thermal_streams(blocks_df, streams_df, flowsheet)
    if not streams:
        return None
    pinch = pinch_analysis(streams, config.dt_min_c)
    util = target_utilities(
        pinch,
        config.steam_levels,
        _compressor_work_mw(blocks_df),
        config.turbine_efficiency,
        config.condenser_temp_c,
        config.dt_min_c,
    )
    return build_energy_kpi(streams, pinch, util, config.dt_min_c)


def figures_for_run(results_dir: Any, spec_dict: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Recompute the pinch result from a run's CSVs and return composite/GCC figures."""
    from . import heat_integration_figures as hif

    rd = Path(results_dir)
    blocks_df = pd.read_csv(rd / "blocks.csv")
    streams_df = pd.read_csv(rd / "streams.csv")
    config = HeatIntegrationConfig.from_spec(spec_dict)
    flowsheet = (spec_dict or {}).get("flowsheet") or []
    streams = extract_thermal_streams(blocks_df, streams_df, flowsheet)
    if not streams:
        return {}
    pinch = pinch_analysis(streams, config.dt_min_c)
    return {
        "heat_composite_curves": hif.fig_composite_curves(
            pinch.hot_composite, pinch.cold_composite
        ),
        "heat_grand_composite": hif.fig_grand_composite(
            pinch.grand_composite, config.steam_levels, config.dt_min_c
        ),
    }
