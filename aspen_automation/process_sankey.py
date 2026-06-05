"""Plotly Sankey diagrams for whole-process mass and energy balances."""
from __future__ import annotations

from typing import Any

import pandas as pd

from .flowsheet_graph import stream_endpoints


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


def sankey_mass_balance(data: dict[str, Any], spec: dict[str, Any]):
    """Whole-process mass-flow Sankey (kg/hr). Each unit is a node; conservation visible."""
    go = _require_plotly()
    producers, consumers = stream_endpoints(spec)
    flows = _mass_flow_lookup(data.get("streams"))

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
    customdata: list[str] = []

    for stream in sorted(set(producers) | set(consumers)):
        value = flows.get(stream)
        if value is None:
            continue
        producer = producers.get(stream)
        dsts = consumers.get(stream, [])
        if producer is None and dsts:
            s, t = node(f"FEED: {stream}"), node(dsts[0])
        elif producer is not None and not dsts:
            s, t = node(producer), node(f"OUT: {stream}")
        elif producer is not None and dsts:
            s, t = node(producer), node(dsts[0])
        else:
            continue
        src_idx.append(s)
        dst_idx.append(t)
        values.append(value)
        customdata.append(stream)

    fig = go.Figure(go.Sankey(
        node=dict(label=labels, pad=18, thickness=16,
                  color="#9ec3e6", line=dict(color="#33536e", width=0.5)),
        link=dict(source=src_idx, target=dst_idx, value=values,
                  customdata=customdata,
                  hovertemplate="%{customdata}: %{value:.0f} kg/hr<extra></extra>"),
    ))
    fig.update_layout(title="Whole-process mass balance (kg/hr)",
                      font=dict(family="Helvetica, Arial, sans-serif", size=12),
                      paper_bgcolor="white", height=520)
    return fig
