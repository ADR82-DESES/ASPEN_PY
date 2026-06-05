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
        node=dict(label=labels, pad=18, thickness=16,
                  color="#b8c4d0", line=dict(color="#33536e", width=0.5)),
        link=dict(source=src_idx, target=dst_idx, value=values, color=link_color,
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
        title="Whole-process mass balance by species (kg/hr)",
        font=dict(family="Helvetica, Arial, sans-serif", size=12),
        paper_bgcolor="white", height=560, showlegend=True,
        legend=dict(title="species", orientation="v", x=1.02, y=1.0),
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

    src_idx: list[int] = []
    dst_idx: list[int] = []
    values: list[float] = []

    if isinstance(df, pd.DataFrame) and not df.empty and "block_name" in df.columns:
        for _, row in df.iterrows():
            name = str(row["block_name"])
            duty = _as_float(row.get("duty_kw")) if "duty_kw" in df.columns else None
            work = _as_float(row.get("net_work_kw")) if "net_work_kw" in df.columns else None
            if duty is not None and duty > 0:
                src_idx.append(index["Utilities"]); dst_idx.append(node(name)); values.append(duty)
            elif duty is not None and duty < 0:
                src_idx.append(node(name)); dst_idx.append(index["Heat removed"]); values.append(-duty)
            if work is not None and work > 0:
                src_idx.append(index["Work"]); dst_idx.append(node(name)); values.append(work)

    fig = go.Figure(go.Sankey(
        node=dict(label=labels, pad=18, thickness=16,
                  color="#f0b67f", line=dict(color="#9a5b2c", width=0.5)),
        link=dict(source=src_idx, target=dst_idx, value=values,
                  hovertemplate="%{value:.0f} kW<extra></extra>"),
    ))
    fig.update_layout(title="Energy balance by unit (kW)",
                      font=dict(family="Helvetica, Arial, sans-serif", size=12),
                      paper_bgcolor="white", height=520)
    return fig
