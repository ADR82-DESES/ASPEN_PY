# Aspen Dashboard v2 (PFD + Sankey + Nature Figures) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the v1 dashboard's Plotly gauge/bars with an equipment-symbol PFD, whole-process mass-balance and energy-balance Sankeys, and Nature-style static figures — rendered inline and exported as SVG/PDF.

**Architecture:** New focused modules (`flowsheet_graph.py`, `process_pfd.py`, `process_sankey.py`, `figure_style.py`) own the connectivity, PFD, Sankey, and Nature-figure concerns; `dashboard.py` keeps only orchestration + export. Heavy libs are lazy-imported; a fallback chain (pyflowsheet → graphviz → mermaid) guarantees a flowsheet always renders.

**Tech Stack:** Python 3.12, pandas, plotly + kaleido (Sankey static export), matplotlib + SciencePlots `nature` (no-latex), python-graphviz (PFD SVG). Managed by Pixi.

---

## REVISION 2026-06-05 (post Task-1 spike): Graphviz-primary PFD

The Task 1 spike proved **pyflowsheet's auto-router is broken** with every installable
`pathfinding` (1.0.x passes a `SimpleHeap` to pyflowsheet's list-based `heapq.heappush`;
the old list-based `0.0.4` violates pyflowsheet's own `>=1.0.1` metadata). A pyflowsheet
PFD would require hand-rolled manual routing. **User decision: use Graphviz as the primary
PFD engine** (clean auto-layout + auto-routing) with equipment-ish node shapes, Mermaid as
the only fallback. Consequences for the tasks below:

- **DROP** `compute_layout` (Graphviz auto-layouts) and the separate `process_pfd.py`
  module. **DROP** the `pyflowsheet` dependency. The PFD lives entirely in
  `flowsheet_graph.py`.
- `block_to_equipment(type) -> category` is KEPT but now maps category → a **Graphviz node
  shape** (reactor/vessel/column→`cylinder`, heater/pump→`circle`, compressor→`trapezium`,
  mixer→`invtriangle`, splitter→`triangle`, valve→`diamond`, blackbox→`box`).
- `build_flowsheet_graphviz(spec)` is upgraded to use those shapes + clean styling and
  returns `("graphviz-svg", svg)` or falls back to `("mermaid", text)`.
- `build_pfd_svg(spec, *, out_path=None) -> (source, svg)` lives in `flowsheet_graph.py`
  (not `process_pfd.py`): try graphviz → fall back to mermaid.
- Renumbered remaining work: **T2** endpoints/edges, **T3** `block_to_equipment` + shape
  map, **T4** move mermaid + equipment-shaped graphviz + `build_pfd_svg` (and drop
  pyflowsheet from pixi), **T5** mass Sankey, **T6** energy Sankey, **T7** nature style +
  synthesis fig, **T8** composition + KPI figs, **T9** dashboard rewire (import PFD from
  `flowsheet_graph`), **T10** codex sync, **T11** full sweep. Tasks 5–10 in the original
  numbering below are superseded where they mention pyflowsheet/`process_pfd`/`compute_layout`.

---

## Reference: confirmed facts (do not re-derive)

- Spec dict: `flowsheet[]={block, inputs:[stream], outputs:[stream]}`, `blocks[]={name, type,...}`.
- `streams.csv` cols: `stream_name, extraction_status, extraction_source, extraction_note, temperature, pressure, mass_flow, mole_flow, <COMP>_mole_frac, <COMP>_mass_frac`.
- `blocks.csv` cols include: `block_name, duty_kw, duty_mw, net_work_kw, ...`.
- `kpis.json`: `methanol_tpd, product_total_tpd, product_stream, purity_fraction, synthesis_loop{co_conversion_fraction, co2_conversion_fraction, h2_consumption_fraction, inlet_stoichiometric_number, inlet_ch4_mole_frac, inlet_co2_mole_frac}`.
- Methanol block types: `MIXER, RGIBBS, HEATER, FLASH2, COMPR, RPLUG, FSPLIT, VALVE, RADFRAC`.
- pyflowsheet: classes for distillation columns, vessels, pumps, compressors, heat exchangers, valves, mixers, splitters, stream flags, `BlackBox`. SVG output. NO auto-layout (caller gives `position=(x,y)`/`size`; it auto-routes streams). API: `Flowsheet(id,title,desc)`, `Unit(name,desc,position=(x,y),size=(w,h))`, `StreamFlag(name,"",position)`, `pfd.addUnits([...])`, `pfd.connect("S01", a["Out"], b["In"])`, `pfd.draw(SvgContext("out.svg"))`. **Exact class names confirmed in Task 1.**
- `dashboard.py` currently defines: `DEFAULT_MERMAID_JS, _node_id, build_flowsheet_mermaid, _read_json, _read_csv, collect_dashboard_data, _require_plotly, _as_float, figure_kpis, figure_synthesis_loop, figure_stream_composition, figure_balances, figure_energy, _html, render_mermaid_html, kpi_cards_html, _all_figures, build_dashboard_html, save_dashboard_html, display_dashboard`. `__init__.py` exports `build_flowsheet_mermaid, collect_dashboard_data, display_dashboard, save_dashboard_html`.

---

## Task 1: Dependencies + pyflowsheet spike

**Files:**
- Modify: `pixi.toml`
- Create: `docs/superpowers/notes/pyflowsheet-spike.md`

- [ ] **Step 1: Add dependencies**

In `pixi.toml` `[dependencies]`, after `nbformat = ">=5.9"`, add:

```toml
matplotlib = ">=3.8"
python-kaleido = ">=0.2"
python-graphviz = ">=0.20"
```

Add a new `[pypi-dependencies]` table at the end of the file (or extend it if present):

```toml
[pypi-dependencies]
pyflowsheet = "*"
scienceplots = ">=2.1"
```

- [ ] **Step 2: Install**

Run: `pixi install`
Expected: solver succeeds; `pixi.lock` updates.
If `pyflowsheet` or `scienceplots` fail to resolve, report BLOCKED with the solver output.

- [ ] **Step 3: Spike — verify imports + minimal renders**

Run:
```bash
pixi run python -c "
import matplotlib, plotly, kaleido, graphviz, scienceplots, pyflowsheet
print('imports OK', matplotlib.__version__)
import inspect, pyflowsheet as pf
print('PYFLOWSHEET CLASSES:', [n for n in dir(pf) if n[0].isupper()])
"
```
Expected: prints `imports OK ...` and a list of pyflowsheet class names (e.g. `BlackBox, Flowsheet, StreamFlag, Mixer, Splitter, ...`).

- [ ] **Step 4: Spike — trivial pyflowsheet SVG + Plotly kaleido export**

Run:
```bash
pixi run python -c "
from pyflowsheet import Flowsheet, BlackBox, StreamFlag, SvgContext
pfd = Flowsheet('F','t','d')
a = BlackBox('A','', position=(100,100), size=(60,40))
f = StreamFlag('FEED','', position=(0,100))
pfd.addUnits([f,a]); pfd.connect('S1', f['Out'], a['In'])
import io
svg = pfd.draw(SvgContext(io.StringIO()))
print('pyflowsheet draw OK')
import plotly.graph_objects as go
fig = go.Figure(go.Sankey(node=dict(label=['x','y']), link=dict(source=[0],target=[1],value=[1])))
fig.to_image(format='svg')
print('kaleido export OK')
"
```
Expected: `pyflowsheet draw OK` and `kaleido export OK`. If the pyflowsheet API differs (constructor signature, `draw`/`SvgContext` usage), record the WORKING calls in the spike note (Step 5) — later tasks must match what actually works.

- [ ] **Step 5: Record findings**

Create `docs/superpowers/notes/pyflowsheet-spike.md` with: confirmed pyflowsheet version, the exact class names available, the exact working constructor/draw/SvgContext calls, the category→class mapping you will use in Task 6, and whether kaleido `to_image(format='svg')` works. This note is the source of truth for Tasks 5–6.

- [ ] **Step 6: Commit**

```bash
git add pixi.toml pixi.lock docs/superpowers/notes/pyflowsheet-spike.md
git commit -m "build: add pyflowsheet/scienceplots/matplotlib/kaleido + spike notes"
```

---

## Task 2: flowsheet_graph — stream endpoints + block edges

**Files:**
- Create: `aspen_automation/flowsheet_graph.py`
- Test: `tests/unit/test_flowsheet_graph.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_flowsheet_graph.py`:

```python
from aspen_automation.flowsheet_graph import stream_endpoints, block_edges

SPEC = {
    "blocks": [{"name": "RX", "type": "RSTOIC"}, {"name": "SEP", "type": "SEP"}],
    "flowsheet": [
        {"block": "RX", "inputs": ["FEED", "RECYCLE"], "outputs": ["RXOUT"]},
        {"block": "SEP", "inputs": ["RXOUT"], "outputs": ["PRODUCT", "RECYCLE"]},
    ],
}


def test_stream_endpoints_producers_and_consumers():
    producers, consumers = stream_endpoints(SPEC)
    assert producers == {"RXOUT": "RX", "PRODUCT": "SEP", "RECYCLE": "SEP"}
    assert consumers == {"FEED": ["RX"], "RECYCLE": ["RX"], "RXOUT": ["SEP"]}


def test_block_edges_internal_only():
    # edges only between blocks (external feeds/products excluded)
    assert block_edges(SPEC) == {("RX", "SEP"), ("SEP", "RX")}
```

- [ ] **Step 2: Run to verify it fails**

Run: `pixi run python -m pytest tests/unit/test_flowsheet_graph.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aspen_automation.flowsheet_graph'`.

- [ ] **Step 3: Implement**

Create `aspen_automation/flowsheet_graph.py`:

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `pixi run python -m pytest tests/unit/test_flowsheet_graph.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add aspen_automation/flowsheet_graph.py tests/unit/test_flowsheet_graph.py
git commit -m "feat(flowsheet-graph): stream endpoints and block edges"
```

---

## Task 3: flowsheet_graph — cycle-safe layered layout

**Files:**
- Modify: `aspen_automation/flowsheet_graph.py`
- Test: `tests/unit/test_flowsheet_graph.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_flowsheet_graph.py`:

```python
from aspen_automation.flowsheet_graph import compute_layout


def test_compute_layout_breaks_recycle_and_layers_left_to_right():
    pos = compute_layout(SPEC, dx=160, dy=120)
    assert set(pos) == {"RX", "SEP"}
    # recycle back-edge removed -> RX upstream of SEP
    assert pos["RX"][0] == 0
    assert pos["SEP"][0] == 160
    # deterministic, no two blocks share a coordinate
    assert len(set(pos.values())) == 2


def test_compute_layout_empty_spec():
    assert compute_layout({}) == {}
```

- [ ] **Step 2: Run to verify it fails**

Run: `pixi run python -m pytest tests/unit/test_flowsheet_graph.py -q`
Expected: FAIL — `ImportError: cannot import name 'compute_layout'`.

- [ ] **Step 3: Implement**

Append to `aspen_automation/flowsheet_graph.py`:

```python
def _block_names(spec: dict[str, Any]) -> list[str]:
    return [
        str(b.get("name"))
        for b in (spec.get("blocks") or [])
        if isinstance(b, dict) and b.get("name")
    ]


def _layers(blocks: list[str], edges: set[tuple[str, str]]) -> dict[str, int]:
    """Longest-path layering after removing DFS back-edges (cycle-safe)."""
    succ: dict[str, set[str]] = defaultdict(set)
    for src, dst in edges:
        succ[src].add(dst)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {b: WHITE for b in blocks}
    back: set[tuple[str, str]] = set()

    def dfs(u: str) -> None:
        color[u] = GRAY
        for v in sorted(succ[u]):
            if color.get(v) == GRAY:
                back.add((u, v))
            elif color.get(v) == WHITE:
                dfs(v)
        color[u] = BLACK

    for b in sorted(blocks):
        if color[b] == WHITE:
            dfs(b)

    pred: dict[str, set[str]] = defaultdict(set)
    for src, dst in edges:
        if (src, dst) not in back:
            pred[dst].add(src)

    layer = {b: 0 for b in blocks}
    for _ in range(len(blocks)):
        changed = False
        for b in blocks:
            for p in pred[b]:
                if layer[b] < layer[p] + 1:
                    layer[b] = layer[p] + 1
                    changed = True
        if not changed:
            break
    return layer


def compute_layout(spec: dict[str, Any], *, dx: int = 160, dy: int = 120) -> dict[str, tuple[int, int]]:
    """Deterministic left-to-right coordinates per block from connectivity."""
    blocks = _block_names(spec)
    if not blocks:
        return {}
    layer = _layers(blocks, block_edges(spec))
    by_layer: dict[int, list[str]] = defaultdict(list)
    for b in sorted(blocks):
        by_layer[layer[b]].append(b)
    positions: dict[str, tuple[int, int]] = {}
    for lvl, members in by_layer.items():
        for slot, b in enumerate(sorted(members)):
            positions[b] = (lvl * dx, slot * dy)
    return positions
```

- [ ] **Step 4: Run to verify it passes**

Run: `pixi run python -m pytest tests/unit/test_flowsheet_graph.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add aspen_automation/flowsheet_graph.py tests/unit/test_flowsheet_graph.py
git commit -m "feat(flowsheet-graph): cycle-safe layered layout"
```

---

## Task 4: flowsheet_graph — move Mermaid builder + add Graphviz fallback

**Files:**
- Modify: `aspen_automation/flowsheet_graph.py`
- Modify: `aspen_automation/dashboard.py` (re-export shim)
- Test: `tests/unit/test_flowsheet_graph.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_flowsheet_graph.py`:

```python
from aspen_automation.flowsheet_graph import build_flowsheet_mermaid, build_flowsheet_graphviz


def test_build_flowsheet_mermaid_here():
    m = build_flowsheet_mermaid(SPEC)
    assert m.startswith("graph LR")
    assert "RX -->|RXOUT| SEP" in m


def test_build_flowsheet_graphviz_returns_dot_or_svg():
    # Returns (source_kind, content). graphviz may render SVG; if the binary is
    # unavailable it must degrade to mermaid, never raise.
    kind, content = build_flowsheet_graphviz(SPEC)
    assert kind in {"graphviz-svg", "mermaid"}
    assert content  # non-empty
```

- [ ] **Step 2: Run to verify it fails**

Run: `pixi run python -m pytest tests/unit/test_flowsheet_graph.py -q`
Expected: FAIL — `ImportError: cannot import name 'build_flowsheet_mermaid'` (not yet in this module).

- [ ] **Step 3: Implement — move mermaid here, add graphviz fallback**

Append to `aspen_automation/flowsheet_graph.py`:

```python
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
    """Best-effort Graphviz SVG; degrade to ('mermaid', <text>) if unavailable."""
    try:
        import graphviz  # type: ignore

        block_types = {
            str(b.get("name")): str(b.get("type", ""))
            for b in (spec.get("blocks") or [])
            if isinstance(b, dict) and b.get("name")
        }
        producers, consumers = stream_endpoints(spec)
        dot = graphviz.Digraph("pfd", graph_attr={"rankdir": "LR"},
                               node_attr={"shape": "box", "style": "rounded,filled",
                                          "fillcolor": "#f5f7fa", "fontname": "Helvetica"})
        for name, btype in block_types.items():
            dot.node(_node_id(name), f"{name}\\n({btype})" if btype else name)
        for stream in sorted(set(producers) | set(consumers)):
            src = producers.get(stream)
            for dst in consumers.get(stream, []):
                if src is not None:
                    dot.edge(_node_id(src), _node_id(dst), label=stream, fontname="Helvetica")
        svg = dot.pipe(format="svg").decode("utf-8")
        return "graphviz-svg", svg
    except Exception:
        return "mermaid", build_flowsheet_mermaid(spec)
```

- [ ] **Step 4: Re-export from dashboard for backward compatibility**

In `aspen_automation/dashboard.py`, find the existing definitions of `_node_id` and `build_flowsheet_mermaid` and DELETE them, then add this import near the top (after `from .process_library import load_process_spec`):

```python
from .flowsheet_graph import _node_id, build_flowsheet_mermaid
```

(`collect_dashboard_data` and the package `__init__` keep working because the name is re-imported here.)

- [ ] **Step 5: Run to verify it passes**

Run: `pixi run python -m pytest tests/unit/test_flowsheet_graph.py tests/unit/test_dashboard.py -q`
Expected: PASS (both files green — the moved mermaid builder still satisfies `test_dashboard.py`'s mermaid tests via the re-export).

- [ ] **Step 6: Commit**

```bash
git add aspen_automation/flowsheet_graph.py aspen_automation/dashboard.py tests/unit/test_flowsheet_graph.py
git commit -m "feat(flowsheet-graph): relocate mermaid builder, add graphviz fallback"
```

---

## Task 5: process_pfd — block-to-equipment category mapping

**Files:**
- Create: `aspen_automation/process_pfd.py`
- Test: `tests/unit/test_process_pfd.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_process_pfd.py`:

```python
import pytest

from aspen_automation.process_pfd import block_to_equipment


@pytest.mark.parametrize("block_type,category", [
    ("MIXER", "mixer"),
    ("FSPLIT", "splitter"),
    ("RADFRAC", "column"),
    ("FLASH2", "vessel"),
    ("HEATER", "heater"),
    ("COMPR", "compressor"),
    ("PUMP", "pump"),
    ("VALVE", "valve"),
    ("RGIBBS", "reactor"),
    ("RPLUG", "reactor"),
    ("RSTOIC", "reactor"),
    ("SOMETHING-ELSE", "blackbox"),
])
def test_block_to_equipment(block_type, category):
    assert block_to_equipment(block_type) == category
```

- [ ] **Step 2: Run to verify it fails**

Run: `pixi run python -m pytest tests/unit/test_process_pfd.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aspen_automation.process_pfd'`.

- [ ] **Step 3: Implement**

Create `aspen_automation/process_pfd.py`:

```python
"""Equipment-symbol process flow diagram (pyflowsheet) with fallbacks."""
from __future__ import annotations

from typing import Any

from .flowsheet_graph import (
    build_flowsheet_graphviz,
    build_flowsheet_mermaid,
    compute_layout,
    stream_endpoints,
)

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


def block_to_equipment(block_type: str) -> str:
    """Map an Aspen block type to a PFD equipment category."""
    return _CATEGORY_BY_TYPE.get(str(block_type).strip().upper(), "blackbox")
```

- [ ] **Step 4: Run to verify it passes**

Run: `pixi run python -m pytest tests/unit/test_process_pfd.py -q`
Expected: PASS (12 passed).

- [ ] **Step 5: Commit**

```bash
git add aspen_automation/process_pfd.py tests/unit/test_process_pfd.py
git commit -m "feat(pfd): block-to-equipment category mapping"
```

---

## Task 6: process_pfd — build_pfd_svg with fallback chain

**Files:**
- Modify: `aspen_automation/process_pfd.py`
- Test: `tests/unit/test_process_pfd.py`

> NOTE: Match the exact pyflowsheet constructor/class names recorded in
> `docs/superpowers/notes/pyflowsheet-spike.md` (Task 1). The code below assumes the
> documented API (`Flowsheet`, `BlackBox`, `StreamFlag`, `SvgContext`, category classes
> `Mixer/Splitter/DistillationColumn/Vessel/HeatExchanger/Compressor/Pump/Valve`). If a
> class name differs, adjust `_EQUIP_CLASS` accordingly — the tests below do not depend on
> the specific classes (they exercise the fallback path).

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_process_pfd.py`:

```python
from aspen_automation.process_pfd import build_pfd_svg

SPEC = {
    "blocks": [{"name": "RX", "type": "RGIBBS"}, {"name": "SEP", "type": "FLASH2"}],
    "flowsheet": [
        {"block": "RX", "inputs": ["FEED"], "outputs": ["RXOUT"]},
        {"block": "SEP", "inputs": ["RXOUT"], "outputs": ["PROD", "OFFGAS"]},
    ],
}


def test_build_pfd_svg_returns_source_and_svg():
    source, svg = build_pfd_svg(SPEC)
    assert source in {"pyflowsheet", "graphviz-svg", "mermaid"}
    assert isinstance(svg, str) and svg.strip()


def test_build_pfd_svg_falls_back_when_pyflowsheet_missing(monkeypatch):
    import aspen_automation.process_pfd as mod
    monkeypatch.setattr(mod, "_render_pyflowsheet", lambda spec, out_path=None: (_ for _ in ()).throw(RuntimeError("no pyflowsheet")))
    source, svg = build_pfd_svg(SPEC)
    assert source in {"graphviz-svg", "mermaid"}
    assert svg.strip()
```

- [ ] **Step 2: Run to verify it fails**

Run: `pixi run python -m pytest tests/unit/test_process_pfd.py -q`
Expected: FAIL — `ImportError: cannot import name 'build_pfd_svg'`.

- [ ] **Step 3: Implement**

Append to `aspen_automation/process_pfd.py`:

```python
def _render_pyflowsheet(spec: dict[str, Any], out_path: str | None = None) -> str:
    """Render an equipment-symbol PFD to an SVG string via pyflowsheet.

    Raises on any problem so the caller can fall back.
    """
    import io

    import pyflowsheet as pf

    # category -> pyflowsheet class (names confirmed in the Task 1 spike note).
    equip_class = {
        "mixer": pf.Mixer,
        "splitter": pf.Splitter,
        "column": pf.DistillationColumn,
        "vessel": pf.Vessel,
        "reactor": pf.Vessel,
        "heater": pf.HeatExchanger,
        "compressor": pf.Compressor,
        "pump": pf.Pump,
        "valve": pf.Valve,
        "blackbox": pf.BlackBox,
    }

    block_types = {
        str(b.get("name")): str(b.get("type", ""))
        for b in (spec.get("blocks") or [])
        if isinstance(b, dict) and b.get("name")
    }
    positions = compute_layout(spec)
    producers, consumers = stream_endpoints(spec)

    pfd = pf.Flowsheet("PFD", "Process Flow Diagram", "")
    units: dict[str, Any] = {}
    for name, btype in block_types.items():
        category = block_to_equipment(btype)
        cls = equip_class.get(category, pf.BlackBox)
        x, y = positions.get(name, (0, 0))
        # +120 keeps everything in positive canvas space, leaving room for feeds at x=0.
        units[name] = cls(name, btype, position=(x + 120, y + 80), size=(60, 40))

    feeds: dict[str, Any] = {}
    for stream in set(producers) | set(consumers):
        if stream not in producers:  # external feed
            dst = consumers.get(stream, [None])[0]
            fx, fy = positions.get(dst, (0, 0)) if dst else (0, 0)
            feeds[stream] = pf.StreamFlag(stream, "", position=(0, fy + 80))
        elif not consumers.get(stream):  # product/purge
            src = producers[stream]
            px, py = positions.get(src, (0, 0))
            feeds[stream] = pf.StreamFlag(stream, "", position=(px + 240, py + 80))

    pfd.addUnits(list(units.values()) + list(feeds.values()))

    n = 0
    for stream in sorted(set(producers) | set(consumers)):
        src = producers.get(stream)
        dsts = consumers.get(stream, [])
        n += 1
        if src is None and dsts:
            pfd.connect(f"S{n}", feeds[stream]["Out"], units[dsts[0]]["In"])
        elif src is not None and not dsts:
            pfd.connect(f"S{n}", units[src]["Out"], feeds[stream]["In"])
        elif src is not None and dsts:
            pfd.connect(f"S{n}", units[src]["Out"], units[dsts[0]]["In"])

    buffer = io.StringIO()
    pfd.draw(pf.SvgContext(buffer))
    svg = buffer.getvalue()
    if out_path:
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write(svg)
    return svg


def build_pfd_svg(spec: dict[str, Any], *, out_path: str | None = None) -> tuple[str, str]:
    """Return (source, svg_or_text). Tries pyflowsheet, then graphviz, then mermaid."""
    try:
        return "pyflowsheet", _render_pyflowsheet(spec, out_path)
    except Exception:
        kind, content = build_flowsheet_graphviz(spec)
        if kind == "graphviz-svg" and out_path:
            with open(out_path, "w", encoding="utf-8") as handle:
                handle.write(content)
        if kind == "graphviz-svg":
            return kind, content
        return "mermaid", build_flowsheet_mermaid(spec)
```

- [ ] **Step 4: Run to verify it passes**

Run: `pixi run python -m pytest tests/unit/test_process_pfd.py -q`
Expected: PASS (14 passed). If `_render_pyflowsheet` raises in the real env because the API differs, the first test still passes via fallback — but fix `_render_pyflowsheet` to match the spike note so `source == "pyflowsheet"` is achievable.

- [ ] **Step 5: Commit**

```bash
git add aspen_automation/process_pfd.py tests/unit/test_process_pfd.py
git commit -m "feat(pfd): pyflowsheet SVG renderer with graphviz/mermaid fallback"
```

---

## Task 7: process_sankey — whole-process mass balance

**Files:**
- Create: `aspen_automation/process_sankey.py`
- Test: `tests/unit/test_process_sankey.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_process_sankey.py`:

```python
import pandas as pd

from aspen_automation.process_sankey import sankey_mass_balance

SPEC = {
    "blocks": [{"name": "RX", "type": "RGIBBS"}, {"name": "SEP", "type": "FLASH2"}],
    "flowsheet": [
        {"block": "RX", "inputs": ["FEED"], "outputs": ["RXOUT"]},
        {"block": "SEP", "inputs": ["RXOUT"], "outputs": ["PROD", "OFFGAS"]},
    ],
}


def _data():
    return {"streams": pd.DataFrame({
        "stream_name": ["FEED", "RXOUT", "PROD", "OFFGAS"],
        "mass_flow": [100.0, 100.0, 60.0, 40.0],
    })}


def test_sankey_mass_balance_is_sankey_with_flow_values():
    fig = sankey_mass_balance(_data(), SPEC)
    assert fig.data[0].type == "sankey"
    labels = list(fig.data[0].node.label)
    # blocks present plus a feed terminal and product/purge terminals
    assert "RX" in labels and "SEP" in labels
    assert any(l.startswith("FEED") for l in labels)
    # link values equal the stream mass flows
    assert sorted(fig.data[0].link.value) == [40.0, 60.0, 100.0, 100.0]


def test_sankey_mass_balance_empty_streams_is_blank():
    fig = sankey_mass_balance({"streams": pd.DataFrame()}, SPEC)
    assert fig.data[0].type == "sankey"
    assert len(fig.data[0].link.value) == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `pixi run python -m pytest tests/unit/test_process_sankey.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aspen_automation.process_sankey'`.

- [ ] **Step 3: Implement**

Create `aspen_automation/process_sankey.py`:

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `pixi run python -m pytest tests/unit/test_process_sankey.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add aspen_automation/process_sankey.py tests/unit/test_process_sankey.py
git commit -m "feat(sankey): whole-process mass-balance Sankey"
```

---

## Task 8: process_sankey — energy balance

**Files:**
- Modify: `aspen_automation/process_sankey.py`
- Test: `tests/unit/test_process_sankey.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_process_sankey.py`:

```python
from aspen_automation.process_sankey import sankey_energy_balance


def test_sankey_energy_balance_routes_by_sign():
    data = {"blocks": pd.DataFrame({
        "block_name": ["B-HEAT", "B-COOL", "B-COMP"],
        "duty_kw": [500.0, -300.0, 0.0],
        "net_work_kw": [0.0, 0.0, 200.0],
    })}
    fig = sankey_energy_balance(data)
    assert fig.data[0].type == "sankey"
    labels = list(fig.data[0].node.label)
    assert "Utilities" in labels and "Heat removed" in labels and "Work" in labels
    # one endothermic (Utilities->B-HEAT), one exothermic (B-COOL->Heat removed), one work
    assert sorted(fig.data[0].link.value) == [200.0, 300.0, 500.0]


def test_sankey_energy_balance_empty_blocks_is_blank():
    fig = sankey_energy_balance({"blocks": pd.DataFrame()})
    assert fig.data[0].type == "sankey"
    assert len(fig.data[0].link.value) == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `pixi run python -m pytest tests/unit/test_process_sankey.py -q`
Expected: FAIL — `ImportError: cannot import name 'sankey_energy_balance'`.

- [ ] **Step 3: Implement**

Append to `aspen_automation/process_sankey.py`:

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `pixi run python -m pytest tests/unit/test_process_sankey.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add aspen_automation/process_sankey.py tests/unit/test_process_sankey.py
git commit -m "feat(sankey): per-unit energy-balance Sankey"
```

---

## Task 9: figure_style — Nature style + synthesis-loop figure

**Files:**
- Create: `aspen_automation/figure_style.py`
- Test: `tests/unit/test_figure_style.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_figure_style.py`:

```python
import matplotlib
matplotlib.use("Agg")  # headless

from aspen_automation.figure_style import use_nature_style, fig_synthesis_loop


def test_use_nature_style_does_not_raise():
    use_nature_style()  # must work even if SciencePlots/LaTeX absent


def test_fig_synthesis_loop_returns_figure_with_bars():
    data = {"kpis": {"synthesis_loop": {
        "co_conversion_fraction": 0.34,
        "co2_conversion_fraction": 0.12,
        "h2_consumption_fraction": 0.40,
    }}}
    fig = fig_synthesis_loop(data)
    ax = fig.axes[0]
    assert len(ax.patches) == 3  # three bars
    assert ax.get_ylabel()
```

- [ ] **Step 2: Run to verify it fails**

Run: `pixi run python -m pytest tests/unit/test_figure_style.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aspen_automation.figure_style'`.

- [ ] **Step 3: Implement**

Create `aspen_automation/figure_style.py`:

```python
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
    labels = ["CO", "CO₂", "H₂"]
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
        ax.set_title(f"Synthesis loop (SN={_as_float(sn):.2f}, target 1.8–2.2)")
    else:
        ax.set_title("Synthesis loop")
    fig.tight_layout()
    return fig
```

- [ ] **Step 4: Run to verify it passes**

Run: `pixi run python -m pytest tests/unit/test_figure_style.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add aspen_automation/figure_style.py tests/unit/test_figure_style.py
git commit -m "feat(figures): nature style + synthesis-loop figure"
```

---

## Task 10: figure_style — composition + KPI summary figures

**Files:**
- Modify: `aspen_automation/figure_style.py`
- Test: `tests/unit/test_figure_style.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_figure_style.py`:

```python
import pandas as pd

from aspen_automation.figure_style import fig_stream_composition, fig_kpi_summary


def test_fig_stream_composition_stacks_components():
    data = {"streams": pd.DataFrame({
        "stream_name": ["FEED", "PROD"],
        "CH4_mole_frac": [0.9, 0.0],
        "H2_mole_frac": [0.1, 0.2],
    })}
    fig = fig_stream_composition(data)
    ax = fig.axes[0]
    assert len(ax.patches) >= 2  # stacked bars across components/streams


def test_fig_kpi_summary_returns_figure():
    data = {"kpis": {"methanol_tpd": 9812, "product_total_tpd": 12000, "purity_fraction": 0.997}}
    fig = fig_kpi_summary(data)
    assert fig.axes  # has at least one axis
```

- [ ] **Step 2: Run to verify it fails**

Run: `pixi run python -m pytest tests/unit/test_figure_style.py -q`
Expected: FAIL — `ImportError: cannot import name 'fig_stream_composition'`.

- [ ] **Step 3: Implement**

Append to `aspen_automation/figure_style.py`:

```python
import pandas as pd


def fig_stream_composition(data: dict[str, Any]):
    """Nature-style stacked mole-fraction composition per stream."""
    import matplotlib.pyplot as plt

    use_nature_style()
    fig, ax = plt.subplots(figsize=(3.6, 2.6))
    df = data.get("streams")
    if isinstance(df, pd.DataFrame) and not df.empty and "stream_name" in df.columns:
        comp_cols = [c for c in df.columns if c.endswith("_mole_frac")]
        bottom = [0.0] * len(df)
        x = list(df["stream_name"])
        for col in comp_cols:
            heights = [float(v) if v == v else 0.0 for v in df[col]]
            ax.bar(x, heights, bottom=bottom, label=col[: -len("_mole_frac")])
            bottom = [b + h for b, h in zip(bottom, heights)]
        ax.set_ylabel("mole fraction")
        ax.legend(fontsize=5, ncol=2, frameon=False)
        for tick in ax.get_xticklabels():
            tick.set_rotation(60)
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `pixi run python -m pytest tests/unit/test_figure_style.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add aspen_automation/figure_style.py tests/unit/test_figure_style.py
git commit -m "feat(figures): composition and KPI-summary nature figures"
```

---

## Task 11: dashboard.py rewire + exports + v1 test cleanup

**Files:**
- Modify: `aspen_automation/dashboard.py`
- Modify: `aspen_automation/__init__.py`
- Modify: `tests/unit/test_dashboard.py`
- Test: `tests/unit/test_dashboard.py`

- [ ] **Step 1: Remove the v1 figure tests and rewrite the export/HTML tests**

In `tests/unit/test_dashboard.py`, DELETE these test functions entirely (they test removed
functions): `test_figure_kpis_is_gauge_with_methanol_value`,
`test_figure_synthesis_loop_bar_labels`, `test_figure_stream_composition_one_trace_per_component`,
`test_figure_stream_composition_empty_is_blank_figure`, `test_figure_balances_in_out_traces`,
`test_figure_energy_per_block_duty_bars`, `test_build_dashboard_html_contains_sections`,
`test_save_dashboard_html_writes_file`. Also remove now-unused imports of those names.

Also UPDATE `test_dashboard_symbols_exported` (it asserts the removed `save_dashboard_html`)
to:

```python
def test_dashboard_symbols_exported():
    assert hasattr(aspen_automation, "display_dashboard")
    assert hasattr(aspen_automation, "collect_dashboard_data")
    assert hasattr(aspen_automation, "build_flowsheet_mermaid")
    assert hasattr(aspen_automation, "save_dashboard_figures")
    assert hasattr(aspen_automation, "build_pfd_svg")
    assert hasattr(aspen_automation, "sankey_mass_balance")
    assert hasattr(aspen_automation, "sankey_energy_balance")
    assert not hasattr(aspen_automation, "save_dashboard_html")
```

Then APPEND new tests:

```python
from aspen_automation.dashboard import build_dashboard_html, save_dashboard_figures


def test_build_dashboard_html_embeds_pfd_and_sankeys(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    _seed_results_dir(results_dir)
    spec = {
        "metadata": {"title": "Methanol Plant"},
        "components": [{"id": "CH4"}],
        "blocks": [{"name": "RX", "type": "RGIBBS"}],
        "flowsheet": [{"block": "RX", "inputs": ["FEED"], "outputs": ["PROD"]}],
    }
    data = collect_dashboard_data(results_dir, spec)
    html = build_dashboard_html(data, spec)
    assert "Methanol Plant" in html
    assert "sankey" in html.lower()        # plotly sankey embedded
    assert "svg" in html.lower()           # PFD svg/mermaid embedded


def test_save_dashboard_figures_writes_files(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    _seed_results_dir(results_dir)
    spec = {"metadata": {"title": "X"}, "components": [{"id": "CH4"}],
            "blocks": [{"name": "RX", "type": "RGIBBS"}],
            "flowsheet": [{"block": "RX", "inputs": ["FEED"], "outputs": ["PROD"]}]}
    paths = save_dashboard_figures(results_dir, tmp_path, spec)
    figdir = tmp_path / "figures"
    assert (figdir / "flowsheet_pfd.svg").is_file()
    assert (figdir / "mass_balance_sankey.svg").is_file()
    assert any(str(p).endswith("synthesis_loop.svg") for p in paths.values())
```

Note: `_seed_results_dir` (Task 3 of the v1 plan) seeds `kpis.json`/`acceptance.json`/
`streams.csv`. Extend it once here to also write a minimal `blocks.csv` so the energy
Sankey/figures have data — add this line inside `_seed_results_dir` before `return tmp_path`:

```python
    (tmp_path / "blocks.csv").write_text(
        "block_name,duty_kw,net_work_kw\nRX,500,0\n", encoding="utf-8")
```

- [ ] **Step 2: Run to verify the new tests fail**

Run: `pixi run python -m pytest tests/unit/test_dashboard.py -q`
Expected: FAIL — `ImportError: cannot import name 'save_dashboard_figures'` (and the new HTML test failing).

- [ ] **Step 3: Rewire `dashboard.py`**

In `aspen_automation/dashboard.py`:

(a) DELETE these functions: `_require_plotly`, `_as_float`, `figure_kpis`,
`figure_synthesis_loop`, `figure_stream_composition`, `figure_balances`, `figure_energy`,
`_all_figures`. (The mermaid builder + `_node_id` were already removed in Task 4.)

(b) Add imports near the top (after the existing `from .flowsheet_graph import ...`):

```python
from .process_pfd import build_pfd_svg
from .process_sankey import sankey_mass_balance, sankey_energy_balance
from . import figure_style
```

(c) REPLACE `build_dashboard_html` with this version (takes `spec`, embeds PFD + Sankeys +
nature figures as inline SVG/PNG):

```python
def _fig_to_svg_data_uri(fig) -> str:
    import base64, io
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f'<img style="max-width:100%" src="data:image/svg+xml;base64,{b64}"/>'


def build_dashboard_html(data: dict[str, Any], spec: dict[str, Any] | None = None) -> str:
    """Assemble a standalone HTML dashboard: KPI cards + PFD + Sankeys + nature figures."""
    spec = spec or {}
    title = (data.get("metadata") or {}).get("title", "Aspen Run Dashboard")
    cards = kpi_cards_html(data)

    _source, pfd_svg = build_pfd_svg(spec)
    pfd_block = pfd_svg if pfd_svg.strip().startswith("<svg") or "<svg" in pfd_svg else (
        f'<pre class="mermaid">{_html.escape(pfd_svg)}</pre>')

    mass = sankey_mass_balance(data, spec).to_html(full_html=False, include_plotlyjs="cdn")
    energy = sankey_energy_balance(data).to_html(full_html=False, include_plotlyjs=False)

    figs = "".join(_fig_to_svg_data_uri(f) for f in (
        figure_style.fig_kpi_summary(data),
        figure_style.fig_synthesis_loop(data),
        figure_style.fig_stream_composition(data),
    ))

    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{_html.escape(str(title))}</title>"
        "<style>body{font-family:Helvetica,Arial,sans-serif;margin:24px;color:#0f172a;}</style>"
        "</head><body>"
        f"<h1>{_html.escape(str(title))}</h1>{cards}"
        f"<h2>Process flow diagram</h2>{pfd_block}"
        f"<h2>Mass balance</h2>{mass}"
        f"<h2>Energy balance</h2>{energy}"
        f"<h2>Key figures</h2>{figs}"
        "</body></html>"
    )
```

(d) ADD `save_dashboard_figures`:

```python
def save_dashboard_figures(
    results_dir: str | Path,
    run_dir: str | Path,
    spec: dict[str, Any] | None = None,
) -> dict[str, Path]:
    """Write publication figures (SVG/PDF) into ``run_dir/figures`` and return the paths."""
    spec = spec or {}
    data = collect_dashboard_data(results_dir, spec)
    figdir = Path(run_dir) / "figures"
    figdir.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}

    _source, pfd_svg = build_pfd_svg(spec, out_path=str(figdir / "flowsheet_pfd.svg"))
    if not (figdir / "flowsheet_pfd.svg").is_file():
        (figdir / "flowsheet_pfd.svg").write_text(pfd_svg, encoding="utf-8")
    out["pfd"] = figdir / "flowsheet_pfd.svg"

    for name, fig in (("mass_balance_sankey", sankey_mass_balance(data, spec)),
                      ("energy_balance_sankey", sankey_energy_balance(data))):
        for ext in ("svg", "pdf"):
            path = figdir / f"{name}.{ext}"
            try:
                fig.write_image(str(path))  # kaleido
                out[f"{name}_{ext}"] = path
            except Exception as exc:  # pragma: no cover - kaleido missing
                print(f"Static export of {name}.{ext} skipped ({exc}).")

    import matplotlib.pyplot as plt
    for name, fig in (("kpi_summary", figure_style.fig_kpi_summary(data)),
                      ("synthesis_loop", figure_style.fig_synthesis_loop(data)),
                      ("stream_composition", figure_style.fig_stream_composition(data))):
        for ext in ("svg", "pdf"):
            path = figdir / f"{name}.{ext}"
            fig.savefig(str(path), bbox_inches="tight")
            out[f"{name}_{ext}"] = path
        plt.close(fig)
    return out
```

(e) REPLACE the body of `display_dashboard` so it shows the new visuals (drop the old
`_all_figures` loop). Replace the section from `display(Markdown("## Results"))` through the
end of the figure loop with:

```python
    _source, pfd_svg = build_pfd_svg(spec or {})
    display(Markdown("## Process flow diagram"))
    if "<svg" in pfd_svg:
        display(HTML(pfd_svg))
    else:
        display(render_mermaid_html(pfd_svg))

    display(Markdown("## Mass balance"))
    sankey_mass_balance(data, spec or {}).show()
    display(Markdown("## Energy balance"))
    sankey_energy_balance(data).show()

    display(Markdown("## Key figures"))
    import matplotlib.pyplot as plt
    for fig in (figure_style.fig_kpi_summary(data),
                figure_style.fig_synthesis_loop(data),
                figure_style.fig_stream_composition(data)):
        display(fig)
        plt.close(fig)
```

Also update `display_dashboard`'s signature to add `save_figures: bool = False` and, before
the final `if save_html:` block, add:

```python
    if save_figures:
        paths = save_dashboard_figures(layout.results_dir, layout.run_dir, spec)
        print(f"Saved {len(paths)} publication figures to {Path(layout.run_dir) / 'figures'}")
```

And change the existing `if save_html:` block to call the new `build_dashboard_html(data, spec)`
signature (it currently builds via `_all_figures`):

```python
    if save_html:
        out = Path(layout.run_dir) / "dashboard.html"
        out.write_text(build_dashboard_html(data, spec), encoding="utf-8")
        print(f"Saved dashboard: {out}")
```

(Remove the now-unused `save_dashboard_html` function and its `_all_figures` dependency; if
`save_dashboard_html` is referenced anywhere else, replace those calls with the inline write
above.)

- [ ] **Step 4: Update package exports**

In `aspen_automation/__init__.py`, replace the dashboard import block and `__all__` entries
to drop `save_dashboard_html` and add the new public names:

```python
from .dashboard import (
    build_dashboard_html,
    collect_dashboard_data,
    display_dashboard,
    save_dashboard_figures,
)
from .flowsheet_graph import build_flowsheet_mermaid, compute_layout
from .process_pfd import build_pfd_svg
from .process_sankey import sankey_mass_balance, sankey_energy_balance
```

And in `__all__` remove `"save_dashboard_html"` and add: `"build_dashboard_html",
"save_dashboard_figures", "compute_layout", "build_pfd_svg", "sankey_mass_balance",
"sankey_energy_balance"` (keep `"build_flowsheet_mermaid"`, `"collect_dashboard_data"`,
`"display_dashboard"`).

- [ ] **Step 5: Run to verify the suite passes**

Run: `pixi run python -m pytest tests/unit/test_dashboard.py tests/unit/test_flowsheet_graph.py tests/unit/test_process_pfd.py tests/unit/test_process_sankey.py tests/unit/test_figure_style.py -q`
Expected: PASS (all green; the deleted v1 figure tests are gone, the new HTML/figure tests pass).

- [ ] **Step 6: Commit**

```bash
git add aspen_automation/dashboard.py aspen_automation/__init__.py tests/unit/test_dashboard.py
git commit -m "feat(dashboard): wire PFD + Sankeys + nature figures, drop v1 charts"
```

---

## Task 12: Sync the `.codex` skill bundle mirror

**Files:**
- Create/Modify under `.codex/skills/antigravity-to-aspen-plus/assets/source/`

- [ ] **Step 1: Copy changed source files into the mirror (scoped)**

Run (Bash):
```bash
base=".codex/skills/antigravity-to-aspen-plus/assets/source"
for f in aspen_automation/dashboard.py aspen_automation/__init__.py \
         aspen_automation/flowsheet_graph.py aspen_automation/process_pfd.py \
         aspen_automation/process_sankey.py aspen_automation/figure_style.py \
         tests/unit/test_dashboard.py tests/unit/test_flowsheet_graph.py \
         tests/unit/test_process_pfd.py tests/unit/test_process_sankey.py \
         tests/unit/test_figure_style.py pixi.toml; do
  mkdir -p "$base/$(dirname "$f")"; cp "$f" "$base/$f";
done
git add $(for f in aspen_automation/dashboard.py aspen_automation/__init__.py \
  aspen_automation/flowsheet_graph.py aspen_automation/process_pfd.py \
  aspen_automation/process_sankey.py aspen_automation/figure_style.py \
  tests/unit/test_dashboard.py tests/unit/test_flowsheet_graph.py \
  tests/unit/test_process_pfd.py tests/unit/test_process_sankey.py \
  tests/unit/test_figure_style.py pixi.toml; do echo "$base/$f"; done)
git status --short "$base"
```
Expected: only the listed dashboard-v2 files are staged under the mirror; pre-existing WIP
(`inp_generator.py`, notebooks, `process.yaml`, `test_inp_generator.py`) is NOT staged.

- [ ] **Step 2: Commit**

```bash
git commit -m "chore(codex): sync dashboard v2 modules into skill bundle mirror"
```

---

## Task 13: Full test sweep

**Files:** none (verification only)

- [ ] **Step 1: Run the unit suite**

Run: `pixi run python -m pytest tests/unit -q`
Expected: all dashboard-v2 tests pass. (One pre-existing unrelated failure may remain:
`test_inp_generator.py::...lights_recovery_section` is user WIP — confirm it is the ONLY
failure and is not caused by these changes via `git stash` of unrelated WIP if needed; do
NOT "fix" it.)

- [ ] **Step 2: Headless end-to-end smoke test on a real run**

Run:
```bash
pixi run python -c "
import tempfile, pathlib
from aspen_automation import load_process_spec, save_dashboard_figures, build_dashboard_html, collect_dashboard_data
results = sorted(pathlib.Path('process_runs/batch_first_capsule/methanol').glob('run_*/results'))[-1]
spec = load_process_spec('process_library/methanol')
paths = save_dashboard_figures(results, tempfile.mkdtemp(), spec)
print('figures written:', len(paths))
html = build_dashboard_html(collect_dashboard_data(results, spec), spec)
print('dashboard.html bytes:', len(html), 'sankey' in html.lower(), 'svg' in html.lower())
"
```
Expected: prints a figure count > 0 and a non-trivial HTML byte count with `True True`. If
pyflowsheet rendered, `flowsheet_pfd.svg` is a real equipment PFD; otherwise the fallback SVG/
mermaid is embedded.

- [ ] **Step 3: Final commit if anything changed**

```bash
git add -A ':!*/inp_generator.py' ':!*test_inp_generator.py' ':!notebooks/*' ':!*/process.yaml'
git commit -m "test(dashboard-v2): green suite + headless smoke" || echo "nothing to commit"
```

---

## Notes for the implementer

- The runner notebooks already call `display_dashboard(result)`, which is preserved — **no
  notebook changes are needed** for v2 (they automatically get the new visuals).
- All heavy libs (matplotlib, plotly, kaleido, pyflowsheet, graphviz, scienceplots) are
  imported lazily inside functions; importing `aspen_automation` must not require them.
- Keep commits scoped — never `git add -A` without the exclusion pathspec in Task 13; the
  working tree carries unrelated user WIP.
