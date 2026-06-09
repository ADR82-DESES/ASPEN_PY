"""Redefine the energy KPI from pinch + power targets; preserve the gross Σ|duty| value."""
from __future__ import annotations

from typing import Any, Dict, List

from .pinch import PinchResult
from .thermal_streams import ThermalStream
from .utility_targeting import UtilityTarget


def build_energy_kpi(
    thermal_streams: List[ThermalStream],
    pinch_result: PinchResult,
    utility_target: UtilityTarget,
    dt_min: float,
) -> Dict[str, Any]:
    # Signed convention: cold duties are positive (heating), hot duties negative
    # (cooling). So gross_cooling_mw is <= 0, and net_duty_mw = heating + cooling.
    gross_heating = sum(s.duty_mw for s in thermal_streams if s.kind == "cold")
    gross_cooling = sum(s.duty_mw for s in thermal_streams if s.kind == "hot")
    gross_abs = sum(abs(s.duty_mw) for s in thermal_streams)
    net_duty = gross_heating + gross_cooling
    energy_consumption = pinch_result.min_hot_utility_mw + utility_target.net_power_mw
    return {
        "energy": {
            "gross_heating_mw": gross_heating,
            "gross_cooling_mw": gross_cooling,
            "net_duty_mw": net_duty,
            "gross_abs_duty_mw": gross_abs,
            "integrated": {
                "dt_min_c": dt_min,
                "pinch_temperature_c": pinch_result.pinch_temperature_c,
                "min_hot_utility_mw": pinch_result.min_hot_utility_mw,
                "min_cold_utility_mw": pinch_result.min_cold_utility_mw,
                "max_recovery_mw": pinch_result.max_recovery_mw,
            },
            "steam_power": {
                "steam_raised_by_level": dict(utility_target.steam_raised_by_level),
                "turbine_power_mw": utility_target.turbine_power_mw,
                "compressor_work_mw": utility_target.compressor_work_mw,
                "net_power_mw": utility_target.net_power_mw,
            },
        },
        "energy_consumption_mw": energy_consumption,
    }
