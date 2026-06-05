"""Pure connectivity + layout helpers derived from a process spec.

No plotting or heavy dependencies — safe to import anywhere.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


def _node_id(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", str(name)) or "n"


def stream_endpoints(spec: dict[str, Any]) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Return (producers, consumers): stream -> producing block, stream -> [consuming blocks]."""
    producers: dict[str, str] = {}
    consumers: dict[str, list[str]] = {}
    for conn in spec.get("flowsheet") or []:
        if not isinstance(conn, dict):
            continue
        block = str(conn.get("block", "")).strip()
        if not block:
            continue
        for stream in conn.get("outputs", []) or []:
            producers[str(stream)] = block
        for stream in conn.get("inputs", []) or []:
            consumers.setdefault(str(stream), []).append(block)
    return producers, consumers


def block_edges(spec: dict[str, Any]) -> set[tuple[str, str]]:
    """Directed block->block edges (a stream that is block A's output and block B's input)."""
    producers, consumers = stream_endpoints(spec)
    edges: set[tuple[str, str]] = set()
    for stream, src in producers.items():
        for dst in consumers.get(stream, []):
            edges.add((src, dst))
    return edges


_CATEGORY_BY_TYPE = {
    "MIXER": "mixer",
    "FSPLIT": "splitter",
    "SSPLIT": "splitter",
    "RADFRAC": "column",
    "DISTL": "column",
    "MULTIFRAC": "column",
    "FLASH2": "vessel",
    "FLASH3": "vessel",
    "FLASH": "vessel",
    "HEATER": "heater",
    "HEATX": "heater",
    "COMPR": "compressor",
    "MCOMPR": "compressor",
    "PUMP": "pump",
    "VALVE": "valve",
    "RGIBBS": "reactor",
    "RSTOIC": "reactor",
    "RPLUG": "reactor",
    "RCSTR": "reactor",
    "REQUIL": "reactor",
    "RYIELD": "reactor",
}

_SHAPE_BY_CATEGORY = {
    "reactor": "cylinder",
    "vessel": "cylinder",
    "column": "cylinder",
    "heater": "circle",
    "pump": "circle",
    "compressor": "trapezium",
    "mixer": "invtriangle",
    "splitter": "triangle",
    "valve": "diamond",
    "blackbox": "box",
}


def block_to_equipment(block_type: str) -> str:
    """Map an Aspen block type to a PFD equipment category."""
    return _CATEGORY_BY_TYPE.get(str(block_type).strip().upper(), "blackbox")


def equipment_shape(category: str) -> str:
    """Map an equipment category to a Graphviz node shape."""
    return _SHAPE_BY_CATEGORY.get(category, "box")


def build_flowsheet_mermaid(spec: dict[str, Any]) -> str:
    """Derive a Mermaid ``graph LR`` from a spec's flowsheet connectivity."""
    producers, consumers = stream_endpoints(spec)
    block_types = {
        str(b.get("name")): str(b.get("type", ""))
        for b in (spec.get("blocks") or [])
        if isinstance(b, dict) and b.get("name")
    }
    block_order = [
        str(c.get("block", "")).strip()
        for c in (spec.get("flowsheet") or [])
        if isinstance(c, dict) and str(c.get("block", "")).strip()
    ]
    seen: set[str] = set()
    lines = ["graph LR"]
    for block in block_order:
        if block in seen:
            continue
        seen.add(block)
        btype = block_types.get(block, "")
        label = f"{block} ({btype})" if btype else block
        lines.append(f'    {_node_id(block)}["{label}"]')

    for stream in sorted(set(producers) | set(consumers)):
        src = producers.get(stream)
        dsts = consumers.get(stream, [])
        if src is None:
            for dst in dsts:
                lines.append(f'    feed_{_node_id(stream)}(["{stream}"]) -->|{stream}| {_node_id(dst)}')
        elif not dsts:
            lines.append(f'    {_node_id(src)} -->|{stream}| out_{_node_id(stream)}(["{stream}"])')
        else:
            for dst in dsts:
                lines.append(f"    {_node_id(src)} -->|{stream}| {_node_id(dst)}")
    return "\n".join(lines)


def build_flowsheet_graphviz(spec: dict[str, Any]) -> tuple[str, str]:
    """Equipment-shaped Graphviz PFD as SVG; degrade to ('mermaid', text) if unavailable."""
    try:
        import graphviz  # type: ignore

        block_types = {
            str(b.get("name")): str(b.get("type", ""))
            for b in (spec.get("blocks") or [])
            if isinstance(b, dict) and b.get("name")
        }
        producers, consumers = stream_endpoints(spec)
        dot = graphviz.Digraph(
            "pfd",
            graph_attr={"rankdir": "LR", "bgcolor": "white", "nodesep": "0.5", "ranksep": "0.8"},
            node_attr={"style": "filled", "fillcolor": "#eef3f8", "color": "#33536e",
                       "fontname": "Helvetica", "fontsize": "10"},
            edge_attr={"fontname": "Helvetica", "fontsize": "8", "color": "#5a6b7b", "arrowsize": "0.7"},
        )
        for name, btype in block_types.items():
            shape = equipment_shape(block_to_equipment(btype))
            label = f"{name}\\n{btype}" if btype else name
            dot.node(_node_id(name), label, shape=shape)
        for stream in sorted(set(producers) | set(consumers)):
            src = producers.get(stream)
            dsts = consumers.get(stream, [])
            if src is None:
                fid = f"feed_{_node_id(stream)}"
                dot.node(fid, stream, shape="plaintext", fillcolor="white")
                for dst in dsts:
                    dot.edge(fid, _node_id(dst), label=stream)
            elif not dsts:
                oid = f"out_{_node_id(stream)}"
                dot.node(oid, stream, shape="plaintext", fillcolor="white")
                dot.edge(_node_id(src), oid, label=stream)
            else:
                for dst in dsts:
                    dot.edge(_node_id(src), _node_id(dst), label=stream)
        svg = dot.pipe(format="svg").decode("utf-8")
        return "graphviz-svg", svg
    except Exception:
        return "mermaid", build_flowsheet_mermaid(spec)


def build_pfd_svg(spec: dict[str, Any], *, out_path: str | None = None) -> tuple[str, str]:
    """Return (source, svg_or_mermaid_text). Graphviz primary, Mermaid fallback."""
    kind, content = build_flowsheet_graphviz(spec)
    if out_path and kind == "graphviz-svg":
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write(content)
    return kind, content
