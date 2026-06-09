"""Convert converged run artifacts into hot/cold thermal streams for pinch analysis."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd

NEAR_ZERO_DUTY_MW = 0.5   # |duty| below this is dropped (noise / no-duty units)
ISOTHERMAL_DT_C = 1.0     # |Tin - Tout| below this is treated as isothermal

REACTOR_TYPES = {"RGIBBS", "RPLUG", "REQUIL"}
SLOPING_TYPES = {"HEATER", "FLASH2"}


@dataclass(frozen=True)
class ThermalStream:
    name: str
    t_supply_c: float
    t_target_c: float
    duty_mw: float          # signed: <0 hot (needs cooling), >0 cold (needs heating)
    kind: str               # "hot" | "cold"
    isothermal: bool

    @property
    def cp_mw_per_c(self) -> float:
        span = abs(self.t_supply_c - self.t_target_c)
        return 0.0 if span == 0 else abs(self.duty_mw) / span


def _num(value: Any) -> Optional[float]:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def _kind(duty_mw: float) -> str:
    return "hot" if duty_mw < 0 else "cold"


def _temps_by_stream(streams_df: pd.DataFrame) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for _, row in streams_df.iterrows():
        name = row.get("stream_name")
        temp = _num(row.get("temperature"))
        if isinstance(name, str) and temp is not None:
            out[name] = temp
    return out


def _io_by_block(flowsheet: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[str]]]:
    out: Dict[str, Dict[str, List[str]]] = {}
    for conn in flowsheet or []:
        block = conn.get("block")
        if isinstance(block, str):
            out[block] = {
                "inputs": list(conn.get("inputs") or []),
                "outputs": list(conn.get("outputs") or []),
            }
    return out


def extract_thermal_streams(
    blocks_df: pd.DataFrame,
    streams_df: pd.DataFrame,
    flowsheet: List[Dict[str, Any]],
) -> List[ThermalStream]:
    temps = _temps_by_stream(streams_df)
    io = _io_by_block(flowsheet)
    streams: List[ThermalStream] = []

    for _, row in blocks_df.iterrows():
        name = row.get("block_name")
        btype = row.get("block_type")
        if not isinstance(name, str) or not isinstance(btype, str):
            continue
        conn = io.get(name, {"inputs": [], "outputs": []})
        inputs, outputs = conn["inputs"], conn["outputs"]

        if btype == "RADFRAC":
            cond = _num(row.get("condenser_duty_mw"))
            reb = _num(row.get("reboiler_duty_mw"))
            dist_t = temps.get(outputs[0]) if len(outputs) >= 1 else None
            bot_t = temps.get(outputs[1]) if len(outputs) >= 2 else None
            if cond is not None and abs(cond) >= NEAR_ZERO_DUTY_MW and dist_t is not None:
                streams.append(
                    ThermalStream(f"{name}-COND", dist_t, dist_t, cond, _kind(cond), True)
                )
            if reb is not None and abs(reb) >= NEAR_ZERO_DUTY_MW and bot_t is not None:
                streams.append(
                    ThermalStream(f"{name}-REB", bot_t, bot_t, reb, _kind(reb), True)
                )
            continue

        duty = _num(row.get("duty_mw"))
        if duty is None or abs(duty) < NEAR_ZERO_DUTY_MW:
            continue

        if btype in REACTOR_TYPES:
            t_out = temps.get(outputs[0]) if outputs else None
            if t_out is None:
                continue
            streams.append(ThermalStream(name, t_out, t_out, duty, _kind(duty), True))
        elif btype in SLOPING_TYPES:
            t_in = temps.get(inputs[0]) if inputs else None
            t_out = temps.get(outputs[0]) if outputs else None
            if t_in is None or t_out is None:
                continue
            if abs(t_in - t_out) < ISOTHERMAL_DT_C:
                streams.append(ThermalStream(name, t_out, t_out, duty, _kind(duty), True))
            else:
                streams.append(ThermalStream(name, t_in, t_out, duty, _kind(duty), False))
        # other block types carry no thermal duty → skipped
    return streams
