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
