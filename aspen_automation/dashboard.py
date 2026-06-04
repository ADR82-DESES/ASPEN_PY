"""Interactive in-notebook dashboard for process runs.

Pure helpers (``build_flowsheet_mermaid``, ``collect_dashboard_data``) have no
plotting/IPython dependency. Chart and render helpers import plotly / IPython
lazily so importing this module never requires them.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from .process_library import load_process_spec

DEFAULT_MERMAID_JS = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs"


def _node_id(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", str(name)) or "n"


def build_flowsheet_mermaid(spec: dict[str, Any]) -> str:
    """Derive a Mermaid ``graph LR`` from a spec's flowsheet connectivity."""
    flowsheet = spec.get("flowsheet") or []
    block_types = {
        str(b.get("name")): str(b.get("type", ""))
        for b in (spec.get("blocks") or [])
        if isinstance(b, dict) and b.get("name")
    }

    producers: dict[str, str] = {}
    consumers: dict[str, list[str]] = {}
    block_order: list[str] = []
    for conn in flowsheet:
        if not isinstance(conn, dict):
            continue
        block = str(conn.get("block", "")).strip()
        if not block:
            continue
        if block not in block_order:
            block_order.append(block)
        for stream in conn.get("outputs", []) or []:
            producers[str(stream)] = block
        for stream in conn.get("inputs", []) or []:
            consumers.setdefault(str(stream), []).append(block)

    lines = ["graph LR"]
    for block in block_order:
        btype = block_types.get(block, "")
        label = f"{block} ({btype})" if btype else block
        lines.append(f'    {_node_id(block)}["{label}"]')

    for stream in sorted(set(producers) | set(consumers)):
        src = producers.get(stream)
        dsts = consumers.get(stream, [])
        if src is None:
            for dst in dsts:
                lines.append(
                    f'    feed_{_node_id(stream)}(["{stream}"]) -->|{stream}| {_node_id(dst)}'
                )
        elif not dsts:
            lines.append(
                f'    {_node_id(src)} -->|{stream}| out_{_node_id(stream)}(["{stream}"])'
            )
        else:
            for dst in dsts:
                lines.append(f"    {_node_id(src)} -->|{stream}| {_node_id(dst)}")

    return "\n".join(lines)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (ValueError, OSError):
        return pd.DataFrame()


def collect_dashboard_data(results_dir: str | Path, spec: dict[str, Any] | None) -> dict[str, Any]:
    """Gather every artifact the dashboard needs from a run's results dir."""
    results_dir = Path(results_dir)
    spec = spec or {}
    components = [
        str(c.get("id"))
        for c in (spec.get("components") or [])
        if isinstance(c, dict) and c.get("id")
    ]
    return {
        "kpis": _read_json(results_dir / "kpis.json"),
        "acceptance": _read_json(results_dir / "acceptance.json"),
        "streams": _read_csv(results_dir / "streams.csv"),
        "blocks": _read_csv(results_dir / "blocks.csv"),
        "material_balance": _read_csv(results_dir / "material_balance.csv"),
        "energy_balance": _read_csv(results_dir / "energy_balance.csv"),
        "flowsheet_mermaid": build_flowsheet_mermaid(spec) if spec else "",
        "components": components,
        "metadata": spec.get("metadata") or {},
    }
