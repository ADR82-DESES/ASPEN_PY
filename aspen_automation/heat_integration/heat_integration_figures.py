"""Composite-curve and grand-composite-curve figures (Nature style)."""
from __future__ import annotations

from typing import List, Sequence, Tuple

from .. import figure_style
from .config import SteamLevel

Curve = Sequence[Tuple[float, float]]


def fig_composite_curves(hot_composite: Curve, cold_composite: Curve):
    figure_style.use_nature_style()
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(3.4, 2.6))
    if hot_composite:
        ht = [t for t, _ in hot_composite]
        hh = [h for _, h in hot_composite]
        ax.plot(hh, ht, color="#c0392b", lw=1.2, label="Hot composite")
    if cold_composite:
        ct = [t for t, _ in cold_composite]
        ch = [h for _, h in cold_composite]
        ax.plot(ch, ct, color="#2471a3", lw=1.2, label="Cold composite")
    ax.set_xlabel("Enthalpy (MW)")
    ax.set_ylabel("Temperature (°C)")
    ax.set_title("Composite curves")
    if hot_composite or cold_composite:
        ax.legend(frameon=False, loc="best")
    fig.tight_layout()
    return fig


def fig_grand_composite(grand_composite: Curve, steam_levels: List[SteamLevel], dt_min: float):
    figure_style.use_nature_style()
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(3.4, 2.6))
    if grand_composite:
        gt = [t for t, _ in grand_composite]
        gh = [h for _, h in grand_composite]
        ax.plot(gh, gt, color="#1e8449", lw=1.2, label="Grand composite")
        shift = dt_min / 2.0
        for lv in steam_levels or []:
            ax.axhline(lv.t_sat_c + shift, color="#7f8c8d", lw=0.6, ls="--")
            ax.text(
                max(gh) if gh else 0.0,
                lv.t_sat_c + shift,
                f" {lv.name}",
                fontsize=6,
                va="center",
                color="#7f8c8d",
            )
    ax.set_xlabel("Net heat flow (MW)")
    ax.set_ylabel("Shifted temperature (°C)")
    ax.set_title("Grand composite curve")
    fig.tight_layout()
    return fig
