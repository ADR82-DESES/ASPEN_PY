"""Steam-level raising + turbine power balance from the grand composite curve."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .config import SteamLevel
from .pinch import Curve, PinchResult

KELVIN = 273.15


@dataclass(frozen=True)
class UtilityTarget:
    steam_raised_by_level: Dict[str, float]
    turbine_power_mw: float
    compressor_work_mw: float
    net_power_mw: float


def _interp_gcc(gcc: Curve, t: float) -> float:
    """Linear interpolation of H at shifted temperature ``t``; gcc sorted T descending."""
    if not gcc:
        return 0.0
    if t >= gcc[0][0]:
        return gcc[0][1]
    if t <= gcc[-1][0]:
        return gcc[-1][1]
    for (t_hi, h_hi), (t_lo, h_lo) in zip(gcc, gcc[1:]):
        if t_lo <= t <= t_hi:
            if t_hi == t_lo:
                return h_lo
            frac = (t - t_lo) / (t_hi - t_lo)
            return h_lo + frac * (h_hi - h_lo)
    return gcc[-1][1]


def target_utilities(
    pinch_result: PinchResult,
    steam_levels: List[SteamLevel],
    compressor_work_mw: float,
    turbine_efficiency: float,
    condenser_temp_c: float,
    dt_min: float,
) -> UtilityTarget:
    shift = dt_min / 2.0
    pinch_t = pinch_result.pinch_temperature_c
    gcc = pinch_result.grand_composite

    levels_hot_first = sorted(steam_levels, key=lambda lv: lv.t_sat_c, reverse=True)
    raised: Dict[str, float] = {}
    prev_cumulative = 0.0
    for lv in levels_hot_first:
        t_shifted = lv.t_sat_c + shift          # steam is a cold sink -> shift up
        if t_shifted >= pinch_t:
            raised[lv.name] = 0.0               # above pinch: not a raising region
            continue
        cumulative = _interp_gcc(gcc, t_shifted)
        raised[lv.name] = max(0.0, cumulative - prev_cumulative)
        prev_cumulative = cumulative

    turbine = 0.0
    for lv in levels_hot_first:
        q = raised.get(lv.name, 0.0)
        if q <= 0.0:
            continue
        carnot = 1.0 - (condenser_temp_c + KELVIN) / (lv.t_sat_c + KELVIN)
        turbine += turbine_efficiency * q * max(0.0, carnot)

    net = compressor_work_mw - turbine
    return UtilityTarget(raised, turbine, compressor_work_mw, net)
