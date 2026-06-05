"""Publication ('Nature') matplotlib figures via SciencePlots + a refined sans theme."""
from __future__ import annotations

from typing import Any

import pandas as pd

_STYLE_APPLIED = False


def use_nature_style() -> None:
    """Apply SciencePlots, then force a Nature-style sans-serif, hairline theme.

    Works even if SciencePlots/LaTeX are unavailable; the rcParams below are applied
    unconditionally so the family is sans-serif (Nature's house style) rather than the
    serif math font SciencePlots' ``science`` style ships with.
    """
    global _STYLE_APPLIED
    import matplotlib.pyplot as plt

    if _STYLE_APPLIED:
        return
    try:
        import scienceplots  # noqa: F401  (registers the styles)
        plt.style.use(["science", "nature", "no-latex"])
    except Exception:
        pass
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "Liberation Sans"],
        "mathtext.fontset": "dejavusans",
        "axes.linewidth": 0.6,
        "axes.edgecolor": "#3f3f3f",
        "axes.titlesize": 8.5,
        "axes.titleweight": "bold",
        "axes.titlepad": 4.0,
        "axes.labelsize": 7.5,
        "axes.labelcolor": "#1a1a1a",
        "text.color": "#1a1a1a",
        "xtick.labelsize": 6.5,
        "ytick.labelsize": 6.5,
        "xtick.color": "#3f3f3f",
        "ytick.color": "#3f3f3f",
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "xtick.top": False,
        "ytick.right": False,
        "xtick.minor.visible": False,
        "ytick.minor.visible": False,
        "legend.fontsize": 6.0,
        "legend.title_fontsize": 6.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 150,
        "savefig.dpi": 600,
        "savefig.bbox": "tight",
    })
    _STYLE_APPLIED = True


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def fig_synthesis_loop(data: dict[str, Any]):
    """Two-panel reaction summary: (a) per-pass conversions, (b) stoichiometric number."""
    import matplotlib.pyplot as plt

    use_nature_style()
    loop = (data.get("kpis") or {}).get("synthesis_loop") or {}
    labels = ["CO", r"CO$_2$", r"H$_2$"]
    values = [
        _as_float(loop.get("co_conversion_fraction")),
        _as_float(loop.get("co2_conversion_fraction")),
        _as_float(loop.get("h2_consumption_fraction")),
    ]
    colors = ["#4c72b0", "#55a868", "#c44e52"]

    fig, (ax, ax_sn) = plt.subplots(
        1, 2, figsize=(3.5, 1.9), gridspec_kw={"width_ratios": [2.1, 1.0]})

    bars = ax.bar(labels, values, color=colors, width=0.64, zorder=2)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.012,
                f"{value * 100:.0f}%", ha="center", va="bottom", fontsize=6)
    ax.set_ylabel("per-pass conversion")
    ax.set_ylim(0, max(0.5, max(values) * 1.3) if values else 0.5)
    ax.grid(axis="y", lw=0.4, color="#e6e6e6", zorder=0)
    ax.set_axisbelow(True)
    ax.set_title("a", loc="left")

    sn = _as_float(loop.get("inlet_stoichiometric_number"))
    ax_sn.axhspan(1.8, 2.2, color="#d6e8d6", zorder=1)
    ax_sn.text(0.06, 2.0, "target", ha="left", va="center", fontsize=5.5, color="#3a6b3a")
    ax_sn.plot([0.55], [sn], marker="D", ms=5.5, color="#c44e52", zorder=3)
    ax_sn.text(0.72, sn, f"{sn:.2f}", ha="left", va="center", fontsize=6.5, fontweight="bold")
    ax_sn.set_xlim(0, 1)
    ax_sn.set_xticks([])
    ax_sn.set_ylim(0, max(2.8, sn * 1.25) if sn else 2.8)
    ax_sn.set_ylabel("stoich. number (SN)")
    ax_sn.set_title("b", loc="left")

    fig.tight_layout(w_pad=1.2)
    return fig


def fig_kpi_summary(data: dict[str, Any]):
    """Bullet-style plant scorecard: methanol output vs 10k target + product purity."""
    import matplotlib.pyplot as plt

    use_nature_style()
    kpis = data.get("kpis") or {}
    methanol = _as_float(kpis.get("methanol_tpd"))
    purity = _as_float(kpis.get("purity_fraction")) * 100.0

    rows = [
        ("Methanol\noutput", methanol / 10000.0, f"{methanol:,.0f} TPD"),
        ("Product\npurity", purity / 100.0, f"{purity:.2f}%"),
    ]
    fig, ax = plt.subplots(figsize=(3.5, 1.35))
    for i, (label, frac, value_text) in enumerate(rows):
        ax.barh(i, 1.0, height=0.5, color="#eceff4", zorder=1)
        ax.barh(i, min(max(frac, 0.0), 1.0), height=0.5, color="#3b6ea5", zorder=2)
        ax.plot([1.0, 1.0], [i - 0.33, i + 0.33], color="#c44e52", lw=1.3, zorder=3)
        ax.text(1.04, i, value_text, va="center", ha="left", fontsize=7)
        ax.text(0.012, i, f"{frac * 100:.0f}% of target", va="center", ha="left",
                fontsize=5.8, color="white" if frac > 0.2 else "#333333", zorder=4)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows])
    ax.set_xlim(0, 1.34)
    ax.set_xticks([])
    ax.invert_yaxis()
    ax.tick_params(length=0)
    ax.set_title("Plant performance vs target", loc="left")
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_visible(False)
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
    fig_height = max(2.6, 0.26 * len(streams) + 0.9)
    fig, ax = plt.subplots(figsize=(5.6, fig_height))
    ax.set_axisbelow(True)
    ax.grid(axis="x", lw=0.4, color="#e6e6e6", zorder=0)

    left = [0.0] * len(streams)
    for col in comp_cols:
        component = col[: -len("_mass_frac")]
        widths = [float(v) if v == v else 0.0 for v in df[col]]
        ax.barh(positions, widths, left=left, height=0.82, label=component,
                color=species_color(component), edgecolor="white", linewidth=0.3, zorder=2)
        left = [acc + w for acc, w in zip(left, widths)]

    ax.set_yticks(positions)
    ax.set_yticklabels(streams, fontsize=6)
    ax.invert_yaxis()  # first stream at the top
    ax.set_xlabel("mass fraction")
    ax.set_xlim(0, 1)
    ax.margins(y=0.005)
    ax.legend(title="species", fontsize=6, frameon=False, handlelength=1.1,
              loc="upper left", bbox_to_anchor=(1.015, 1.0))
    fig.tight_layout()
    return fig
