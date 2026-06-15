"""Configuration for heat-integration pinch analysis.

Defaults model a typical methanol/ATR utility system. Override via an optional
``heat_integration`` block in process.yaml.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class SteamLevel:
    """A steam header: name, saturation temperature (°C), header pressure (bar)."""

    name: str
    t_sat_c: float
    pressure_bar: float


# Saturation temperatures: 100 bar ≈ 311 °C, 40 bar ≈ 250 °C, 6 bar ≈ 159 °C.
# A tuple so the shared default cannot be mutated in place.
DEFAULT_STEAM_LEVELS: Tuple[SteamLevel, ...] = (
    SteamLevel("HP", 311.0, 100.0),
    SteamLevel("MP", 250.0, 40.0),
    SteamLevel("LP", 159.0, 6.0),
)


@dataclass(frozen=True)
class HeatIntegrationConfig:
    dt_min_c: float = 10.0
    # Tuple keeps the frozen contract real: the field reference *and* its contents
    # are immutable. Callers that iterate or sort the levels work unchanged.
    steam_levels: Tuple[SteamLevel, ...] = DEFAULT_STEAM_LEVELS
    turbine_efficiency: float = 0.80
    condenser_temp_c: float = 40.0

    @classmethod
    def from_spec(cls, spec: Optional[Dict[str, Any]]) -> "HeatIntegrationConfig":
        block = spec.get("heat_integration") if isinstance(spec, dict) else None
        if not isinstance(block, dict):
            return cls()
        dt_min = float(block.get("dt_min", block.get("dt_min_c", 10.0)))
        eff = float(block.get("turbine_efficiency", 0.80))
        cond = float(block.get("condenser_temp_c", 40.0))
        levels_raw = block.get("steam_levels")
        levels: Tuple[SteamLevel, ...] = DEFAULT_STEAM_LEVELS
        if isinstance(levels_raw, list) and levels_raw:
            parsed = tuple(
                SteamLevel(
                    str(lv.get("name", f"L{i}")),
                    float(lv["t_sat_c"]),
                    float(lv.get("pressure_bar", 0.0)),
                )
                for i, lv in enumerate(levels_raw)
                if isinstance(lv, dict) and "t_sat_c" in lv
            )
            if parsed:  # ignore a list whose entries are all malformed
                levels = parsed
        return cls(
            dt_min_c=dt_min,
            steam_levels=levels,
            turbine_efficiency=eff,
            condenser_temp_c=cond,
        )
