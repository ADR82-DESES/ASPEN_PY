"""Fixed, shared color code for chemical species across all dashboard figures.

Pure (a dict + two functions) so it can be imported by both the Sankey and the
matplotlib figures without pulling any heavy dependency.
"""
from __future__ import annotations

import hashlib
from typing import Iterable

# One distinct, fixed color per common component id. Used identically by the
# species-resolved mass Sankey and the stream-composition figure so a species is
# always the same color everywhere.
SPECIES_PALETTE: dict[str, str] = {
    "CH4": "#1f77b4",    # blue
    "H2O": "#17becf",    # cyan
    "O2": "#0d9488",     # teal
    "CO": "#ff7f0e",     # orange
    "CO2": "#d62728",    # red
    "H2": "#2ca02c",     # green
    "CH3OH": "#9467bd",  # purple
    "N2": "#7f7f7f",     # grey
}

# Deterministic fallback colors for components not in the fixed palette.
_FALLBACK = [
    "#8c564b", "#e377c2", "#bcbd22", "#aec7e8",
    "#ffbb78", "#98df8a", "#c5b0d5", "#c49c94",
]


def species_color(component_id: str) -> str:
    """Return the fixed hex color for a component (case-insensitive).

    Unknown components get a deterministic, stable color from the fallback list.
    """
    cid = str(component_id).strip().upper()
    if cid in SPECIES_PALETTE:
        return SPECIES_PALETTE[cid]
    digest = int(hashlib.md5(cid.encode("utf-8")).hexdigest(), 16)
    return _FALLBACK[digest % len(_FALLBACK)]


def species_color_map(component_ids: Iterable[str]) -> dict[str, str]:
    """Map each component id to its color (for building legends)."""
    return {str(cid): species_color(cid) for cid in component_ids}
