"""Plotly Sankey diagrams for whole-process mass and energy balances."""
from __future__ import annotations

from typing import Any

import pandas as pd

from .flowsheet_graph import stream_endpoints
from .species_colors import species_color


def _require_plotly():
    try:
        import plotly.graph_objects as go
    except ImportError as exc:  # pragma: no cover - environment guard
        raise ImportError("plotly is required for Sankey diagrams; run `pixi install`.") from exc
    return go


def _rgba(hex_color: str, alpha: float) -> str:
    """Translucent rgba() string from a #rrggbb hex (for softer, overlap-readable links)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


_SANKEY_FONT = dict(family="Arial, Helvetica, sans-serif", size=12, color="#1a1a1a")


def _mass_flow_lookup(streams: Any) -> dict[str, float]:
    if not isinstance(streams, pd.DataFrame) or streams.empty or "stream_name" not in streams.columns:
        return {}
    if "mass_flow" not in streams.columns:
        return {}
    out: dict[str, float] = {}
    for _, row in streams.iterrows():
        try:
            out[str(row["stream_name"])] = float(row["mass_flow"])
        except (TypeError, ValueError):
            continue
    return out


def _mass_fraction_lookup(streams: Any) -> dict[str, dict[str, float]]:
    """stream_name -> {component: mass_fraction>0} from the ``<COMP>_mass_frac`` columns."""
    if not isinstance(streams, pd.DataFrame) or streams.empty or "stream_name" not in streams.columns:
        return {}
    frac_cols = [c for c in streams.columns if c.endswith("_mass_frac")]
    out: dict[str, dict[str, float]] = {}
    for _, row in streams.iterrows():
        comps: dict[str, float] = {}
        for col in frac_cols:
            component = col[: -len("_mass_frac")]
            try:
                frac = float(row[col])
            except (TypeError, ValueError):
                continue
            if frac == frac and frac > 0:  # skip NaN and zero/negative
                comps[component] = frac
        if comps:
            out[str(row["stream_name"])] = comps
    return out


def stream_styles(streams: Any) -> tuple[dict[str, float], dict[str, str]]:
    """Return (mass_flow_by_stream, dominant_species_by_stream) for PFD edge styling."""
    flows = _mass_flow_lookup(streams)
    fracs = _mass_fraction_lookup(streams)
    dominant: dict[str, str] = {}
    for stream, comps in fracs.items():
        if comps:
            dominant[stream] = max(comps, key=comps.get)
    return flows, dominant


def sankey_mass_balance(data: dict[str, Any], spec: dict[str, Any]):
    """Whole-process mass-flow Sankey (kg/hr).

    Each unit is a node; a stream is routed to every consuming block (fan-out). For
    the common point-to-point case this means per-node mass conservation is visible.
    """
    go = _require_plotly()
    producers, consumers = stream_endpoints(spec)
    flows = _mass_flow_lookup(data.get("streams"))
    fracs = _mass_fraction_lookup(data.get("streams"))

    labels: list[str] = []
    index: dict[str, int] = {}

    def node(label: str) -> int:
        if label not in index:
            index[label] = len(labels)
            labels.append(label)
        return index[label]

    src_idx: list[int] = []
    dst_idx: list[int] = []
    values: list[float] = []
    link_color: list[str] = []
    customdata: list[str] = []
    species_present: list[str] = []  # first-seen order, for the legend
    total_color = "#cccccc"

    def add_link(source: int, target: int, value: float, color: str, label: str) -> None:
        src_idx.append(source)
        dst_idx.append(target)
        values.append(value)
        link_color.append(color)
        customdata.append(label)

    for stream in sorted(set(producers) | set(consumers)):
        value = flows.get(stream)
        if value is None:
            continue
        producer = producers.get(stream)
        dsts = consumers.get(stream, [])
        if producer is None and dsts:
            source_node = node(f"FEED: {stream}")
            targets = [node(dst) for dst in dsts]
        elif producer is not None and not dsts:
            source_node = node(producer)
            targets = [node(f"OUT: {stream}")]
        elif producer is not None and dsts:
            source_node = node(producer)
            targets = [node(dst) for dst in dsts]
        else:
            continue
        comp_fracs = fracs.get(stream)
        # Fan out to every consumer; split each link into per-species sub-links so a
        # stream's width is the sum of its components (consistent color per species).
        for target_node in targets:
            if comp_fracs:
                for component, frac in comp_fracs.items():
                    add_link(source_node, target_node, value * frac,
                             species_color(component), f"{stream} · {component}")
                    if component not in species_present:
                        species_present.append(component)
            else:
                add_link(source_node, target_node, value, total_color, f"{stream} · total")

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=labels, pad=24, thickness=18,
                  color="#e2e8f0", line=dict(color="#94a3b8", width=0.4)),
        textfont=dict(color="#1a1a1a", size=11, family="Arial, Helvetica, sans-serif"),
        link=dict(source=src_idx, target=dst_idx, value=values,
                  color=[_rgba(c, 0.6) for c in link_color],
                  customdata=customdata,
                  hovertemplate="%{customdata}: %{value:.0f} kg/hr<extra></extra>"),
    ))
    # Plotly Sankey has no native legend; add hidden marker traces so each species
    # appears as a colored legend entry.
    for component in species_present:
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers", name=component,
            marker=dict(size=10, color=species_color(component)), showlegend=True,
        ))
    fig.update_layout(
        title=dict(text="Whole-process mass balance by species (kg/hr)",
                   font=dict(size=15, color="#1a1a1a")),
        font=_SANKEY_FONT, paper_bgcolor="white", plot_bgcolor="white",
        height=660, margin=dict(l=12, r=120, t=48, b=12), showlegend=True,
        legend=dict(title=dict(text="species"), orientation="v", x=1.01, y=1.0,
                    bgcolor="rgba(255,255,255,0)", font=dict(size=11)),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
    )
    return fig


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def sankey_energy_balance(data: dict[str, Any]):
    """Per-unit energy Sankey from block duties/work (kW)."""
    go = _require_plotly()
    df = data.get("blocks")

    labels: list[str] = ["Utilities", "Heat removed", "Work"]
    index = {label: i for i, label in enumerate(labels)}

    def node(label: str) -> int:
        if label not in index:
            index[label] = len(labels)
            labels.append(label)
        return index[label]

    cat_color = {"heat in": "#e8a87c", "heat out": "#7fb3d5", "work": "#b39ddb"}

    src_idx: list[int] = []
    dst_idx: list[int] = []
    values: list[float] = []
    link_color: list[str] = []

    def add(source: int, target: int, value: float, category: str) -> None:
        src_idx.append(source)
        dst_idx.append(target)
        values.append(value)
        link_color.append(_rgba(cat_color[category], 0.6))

    if isinstance(df, pd.DataFrame) and not df.empty and "block_name" in df.columns:
        for _, row in df.iterrows():
            name = str(row["block_name"])
            duty = _as_float(row.get("duty_kw")) if "duty_kw" in df.columns else None
            work = _as_float(row.get("net_work_kw")) if "net_work_kw" in df.columns else None
            if duty is not None and duty > 0:
                add(index["Utilities"], node(name), duty, "heat in")
            elif duty is not None and duty < 0:
                add(node(name), index["Heat removed"], -duty, "heat out")
            if work is not None and work > 0:
                add(index["Work"], node(name), work, "work")

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=labels, pad=22, thickness=18,
                  color="#e2e8f0", line=dict(color="#94a3b8", width=0.4)),
        textfont=dict(color="#1a1a1a", size=11, family="Arial, Helvetica, sans-serif"),
        link=dict(source=src_idx, target=dst_idx, value=values, color=link_color,
                  hovertemplate="%{value:.0f} kW<extra></extra>"),
    ))
    for label, category in (("heat in (utilities)", "heat in"),
                            ("heat removed", "heat out"), ("shaft work", "work")):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers", name=label,
            marker=dict(size=10, color=cat_color[category]), showlegend=True,
        ))
    fig.update_layout(
        title=dict(text="Energy balance by unit (kW)", font=dict(size=15, color="#1a1a1a")),
        font=_SANKEY_FONT, paper_bgcolor="white", plot_bgcolor="white",
        height=560, margin=dict(l=12, r=130, t=48, b=12), showlegend=True,
        legend=dict(orientation="v", x=1.01, y=1.0, bgcolor="rgba(255,255,255,0)",
                    font=dict(size=11)),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
    )
    return fig
