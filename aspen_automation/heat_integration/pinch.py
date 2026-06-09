"""Problem Table Algorithm: pinch targets + composite / grand-composite curves.

Sensible streams contribute CP·ΔT across shifted-temperature intervals. Isothermal
(latent) streams contribute their whole duty as a point load at their shifted
temperature. Sign convention: a stream's contribution to interval *surplus* is
``-duty_mw`` (hot duty<0 -> +surplus; cold duty>0 -> -surplus).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from .thermal_streams import ThermalStream

Curve = List[Tuple[float, float]]


@dataclass(frozen=True)
class PinchResult:
    pinch_temperature_c: float          # shifted (mean) pinch temperature: the node where the
    #                                     feasible cascade is minimum; the highest-T such node
    #                                     if several tie (min() over descending-T nodes)
    min_hot_utility_mw: float
    min_cold_utility_mw: float
    max_recovery_mw: float
    grand_composite: Curve              # (shifted_T, net heat flow H), descending T
    hot_composite: Curve                # (actual_T, cumulative H), ascending T
    cold_composite: Curve               # (actual_T, cumulative H), ascending T


def _shifted_endpoints(s: ThermalStream, shift: float) -> Tuple[float, float]:
    if s.kind == "hot":
        return s.t_supply_c - shift, s.t_target_c - shift
    return s.t_supply_c + shift, s.t_target_c + shift


def _one_composite(streams_of_kind: List[ThermalStream]) -> Curve:
    if not streams_of_kind:
        return []
    bounds = set()
    for s in streams_of_kind:
        bounds.add(round(min(s.t_supply_c, s.t_target_c), 6))
        bounds.add(round(max(s.t_supply_c, s.t_target_c), 6))
    temps = sorted(bounds)            # ascending (cold end first)
    curve: Curve = [(temps[0], 0.0)]
    h = 0.0
    for i in range(len(temps) - 1):
        t_lo, t_hi = temps[i], temps[i + 1]
        iso = sum(
            abs(s.duty_mw) for s in streams_of_kind
            if s.isothermal and round(s.t_supply_c, 6) == round(t_lo, 6)
        )
        if iso:
            h += iso
            curve.append((t_lo, h))   # vertical jump at the latent temperature
        cp = sum(
            s.cp_mw_per_c for s in streams_of_kind
            if not s.isothermal
            # round to the grid precision: temps come from round(..., 6) bounds, so the
            # endpoints must be rounded too or a stream is dropped at its own boundary.
            and round(min(s.t_supply_c, s.t_target_c), 6) <= t_lo
            and round(max(s.t_supply_c, s.t_target_c), 6) >= t_hi
        )
        h += cp * (t_hi - t_lo)
        curve.append((t_hi, h))
    top = temps[-1]
    iso_top = sum(
        abs(s.duty_mw) for s in streams_of_kind
        if s.isothermal and round(s.t_supply_c, 6) == round(top, 6)
    )
    if iso_top:
        h += iso_top
        curve.append((top, h))
    return curve


def build_composite_curves(streams: List[ThermalStream]) -> Tuple[Curve, Curve]:
    hot = _one_composite([s for s in streams if s.kind == "hot"])
    cold = _one_composite([s for s in streams if s.kind == "cold"])
    return hot, cold


def pinch_analysis(streams: List[ThermalStream], dt_min: float) -> PinchResult:
    shift = dt_min / 2.0
    sensible = [s for s in streams if not s.isothermal]
    isothermal = [s for s in streams if s.isothermal]

    bounds = set()
    for s in streams:
        a, b = _shifted_endpoints(s, shift)
        bounds.add(round(a, 6))
        bounds.add(round(b, 6))
    temps = sorted(bounds, reverse=True)

    hot_c, cold_c = build_composite_curves(streams)
    total_hot = sum(-s.duty_mw for s in streams if s.kind == "hot")

    if len(temps) < 2:
        surplus = sum(-s.duty_mw for s in streams)
        q_hmin = max(0.0, -surplus)
        q_cmin = max(0.0, surplus)
        pt = temps[0] if temps else 0.0
        return PinchResult(pt, q_hmin, q_cmin, max(0.0, total_hot - q_cmin),
                           [(pt, q_hmin)], hot_c, cold_c)

    iso_load = {t: 0.0 for t in temps}
    for s in isothermal:
        a, _ = _shifted_endpoints(s, shift)
        key = round(a, 6)
        iso_load[key] = iso_load.get(key, 0.0) + (-s.duty_mw)   # hot +, cold -

    def sensible_surplus(t_lo: float, t_hi: float) -> float:
        cp_hot = cp_cold = 0.0
        for s in sensible:
            a, b = _shifted_endpoints(s, shift)
            # round to the grid precision (temps are rounded bounds) so a stream is not
            # dropped at its own boundary interval by a sub-1e-6 float difference.
            a, b = round(a, 6), round(b, 6)
            s_hi, s_lo = max(a, b), min(a, b)
            if s_lo <= t_lo and s_hi >= t_hi:
                if s.kind == "hot":
                    cp_hot += s.cp_mw_per_c
                else:
                    cp_cold += s.cp_mw_per_c
        return (cp_hot - cp_cold) * (t_hi - t_lo)

    h = iso_load.get(temps[0], 0.0)
    nodes: Curve = [(temps[0], h)]
    for i in range(len(temps) - 1):
        t_hi, t_lo = temps[i], temps[i + 1]
        h += sensible_surplus(t_lo, t_hi)
        h += iso_load.get(t_lo, 0.0)
        nodes.append((t_lo, h))

    h_values = [hv for _, hv in nodes]
    q_hmin = max(0.0, -min(h_values))
    feasible = [(t, hv + q_hmin) for t, hv in nodes]
    q_cmin = feasible[-1][1]
    pinch_t = min(feasible, key=lambda p: p[1])[0]
    max_recovery = total_hot - q_cmin

    return PinchResult(
        pinch_temperature_c=pinch_t,
        min_hot_utility_mw=q_hmin,
        min_cold_utility_mw=q_cmin,
        max_recovery_mw=max_recovery,
        grand_composite=feasible,
        hot_composite=hot_c,
        cold_composite=cold_c,
    )
