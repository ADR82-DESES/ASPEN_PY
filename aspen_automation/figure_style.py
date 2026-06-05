"""Publication ('Nature') matplotlib figures via SciencePlots, with graceful fallback."""
from __future__ import annotations

from typing import Any

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
