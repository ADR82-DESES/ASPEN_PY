"""Publication ('Nature') matplotlib figures via SciencePlots, with graceful fallback."""
from __future__ import annotations

from typing import Any

import pandas as pd

_STYLE_APPLIED = False


def use_nature_style() -> None:
    """Apply SciencePlots ['science','nature','no-latex']; fall back to plain rcParams."""
    global _STYLE_APPLIED
    import matplotlib.pyplot as plt

    if _STYLE_APPLIED:
        return
    try:
        import scienceplots  # noqa: F401  (registers styles)
        plt.style.use(["science", "nature", "no-latex"])
    except Exception:
        plt.rcParams.update({
            "font.family": "sans-serif",
            "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 300,
            "savefig.dpi": 300,
        })
    _STYLE_APPLIED = True


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def fig_synthesis_loop(data: dict[str, Any]):
    """Nature-style grouped conversion bars with the SN target band annotated."""
    import matplotlib.pyplot as plt

    use_nature_style()
    loop = (data.get("kpis") or {}).get("synthesis_loop") or {}
    labels = ["CO", r"CO$_2$", r"H$_2$"]
    values = [
        _as_float(loop.get("co_conversion_fraction")),
        _as_float(loop.get("co2_conversion_fraction")),
        _as_float(loop.get("h2_consumption_fraction")),
    ]
    fig, ax = plt.subplots(figsize=(3.3, 2.5))
    ax.bar(labels, values, color=["#4c72b0", "#55a868", "#c44e52"])
    ax.set_ylabel("conversion / use (fraction)")
    ax.set_ylim(0, 1)
    sn = loop.get("inlet_stoichiometric_number")
    if sn is not None:
        ax.set_title(f"Synthesis loop (SN={_as_float(sn):.2f}, target 1.8-2.2)")
    else:
        ax.set_title("Synthesis loop")
    fig.tight_layout()
    return fig


def fig_stream_composition(data: dict[str, Any]):
    """Nature-style horizontal stacked mass-fraction composition per stream.

    Horizontal bars keep every stream name legible even with ~30 streams; species
    use the shared color code and the legend sits outside the plot.
    """
    import matplotlib.pyplot as plt

    from .species_colors import species_color

    use_nature_style()
    df = data.get("streams")
    if not (isinstance(df, pd.DataFrame) and not df.empty and "stream_name" in df.columns):
        fig, _ = plt.subplots(figsize=(3.6, 2.6))
        fig.tight_layout()
        return fig

    comp_cols = [c for c in df.columns if c.endswith("_mass_frac")]
    streams = [str(s) for s in df["stream_name"]]
    positions = list(range(len(streams)))
    fig_height = max(2.5, 0.28 * len(streams) + 1.0)
    fig, ax = plt.subplots(figsize=(5.4, fig_height))

    left = [0.0] * len(streams)
    for col in comp_cols:
        component = col[: -len("_mass_frac")]
        widths = [float(v) if v == v else 0.0 for v in df[col]]
        ax.barh(positions, widths, left=left, label=component, color=species_color(component))
        left = [acc + w for acc, w in zip(left, widths)]

    ax.set_yticks(positions)
    ax.set_yticklabels(streams, fontsize=6)
    ax.invert_yaxis()  # first stream at the top
    ax.set_xlabel("mass fraction")
    ax.set_xlim(0, 1)
    ax.legend(title="species", fontsize=6, frameon=False,
              loc="upper left", bbox_to_anchor=(1.02, 1.0))
    fig.tight_layout()
    return fig


def fig_kpi_summary(data: dict[str, Any]):
    """Nature-style headline: methanol production vs the 10k TPD target."""
    import matplotlib.pyplot as plt

    use_nature_style()
    kpis = data.get("kpis") or {}
    methanol = _as_float(kpis.get("methanol_tpd"))
    fig, ax = plt.subplots(figsize=(3.3, 2.3))
    ax.bar(["Methanol"], [methanol], color="#4c72b0", width=0.5)
    ax.axhline(10000, color="#c44e52", linestyle="--", linewidth=1)
    ax.text(0, 10000, " 10k TPD target", va="bottom", ha="left", fontsize=6, color="#c44e52")
    ax.set_ylabel("production (TPD)")
    purity = kpis.get("purity_fraction")
    ax.set_title(f"Methanol {methanol:.0f} TPD"
                 + (f", purity {_as_float(purity) * 100:.1f}%" if purity is not None else ""))
    fig.tight_layout()
    return fig
