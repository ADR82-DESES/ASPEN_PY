# Aspen Run Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an interactive, in-notebook dashboard that visualizes a process run's flowsheet (Mermaid) and results (Plotly), rendered from already-saved run artifacts.

**Architecture:** A new `aspen_automation/dashboard.py` separates pure data-gathering and string-building (testable, no browser) from rendering. `collect_dashboard_data` reads the run's `results/` CSV/JSON artifacts; `build_flowsheet_mermaid` derives a Mermaid graph from the spec connectivity; `figure_*` functions return Plotly figures; `render_mermaid_html` returns an IPython `HTML` iframe; `display_dashboard` orchestrates inline display; `save_dashboard_html` writes an optional standalone `dashboard.html`. Plotly/IPython imports are lazy so importing the package never requires them.

**Tech Stack:** Python 3.12, pandas, plotly (new dep), Mermaid.js (CDN, in an iframe), IPython display, pytest. Managed by Pixi.

---

## Reference: confirmed data shapes (do not guess — these are verified from the codebase)

- `result` is `aspen_automation.process_library.ProcessRunResult` with:
  `process_name: str`, `process_dir: Path`, `status: str`, `succeeded: bool` (property),
  `layout: ProcessLayout | None`, `details: dict`.
- `ProcessLayout` fields: `run_dir: Path`, `results_dir: Path` (among others).
- `load_process_spec(process_dir) -> dict` (exported from `aspen_automation`) returns the
  spec dict with keys: `metadata` (`{title, ...}`), `components` (`[{id, name, ...}]`),
  `flowsheet` (`[{block, inputs:[stream], outputs:[stream]}]`), `blocks` (`[{name, type, ...}]`),
  `streams` (`[{name, ...}]`).
- Artifacts in `results_dir`:
  - `kpis.json` → `{product_stream, product_total_tpd, methanol_tpd, product_component_tpd, convergence_status?, synthesis_loop: {co_conversion_fraction, co2_conversion_fraction, h2_consumption_fraction, inlet_stoichiometric_number, inlet_ch4_mole_frac, inlet_co2_mole_frac, methanol_formation_kmol_hr, ...}}`
  - `acceptance.json` → `{passed: bool, ...}`
  - `streams.csv` columns: `stream_name, extraction_status, extraction_source, extraction_note, temperature, pressure, mass_flow, mole_flow, <COMP>_mole_frac, <COMP>_mass_frac, ...`
  - `blocks.csv` columns include: `block_name, ..., duty_kw, duty_mw, ...`
  - `material_balance.csv` columns: `component_id, component, input_kmol_hr, output_kmol_hr, closure_pct, closure_%`
  - `energy_balance.csv` (block-derived; columns vary — read defensively).

---

## Task 1: Add Plotly dependency to the Pixi environment

**Files:**
- Modify: `pixi.toml` (`[dependencies]` table)

- [ ] **Step 1: Add the dependencies**

In `pixi.toml`, under `[dependencies]`, add two lines after `notebook = ">=7.0"`:

```toml
plotly = ">=5.20"
nbformat = ">=5.9"
```

- [ ] **Step 2: Install**

Run: `pixi install`
Expected: solves and installs `plotly` and `nbformat` (and updates `pixi.lock`).

- [ ] **Step 3: Verify import in the pixi env**

Run: `pixi run python -c "import plotly.graph_objects as go; import nbformat; print('ok', plotly.__version__)"`
Expected: prints `ok` and a version (no ImportError).

- [ ] **Step 4: Commit**

```bash
git add pixi.toml pixi.lock
git commit -m "build: add plotly + nbformat for run dashboard"
```

---

## Task 2: Flowsheet Mermaid builder

**Files:**
- Create: `aspen_automation/dashboard.py`
- Test: `tests/unit/test_dashboard.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_dashboard.py`:

```python
from aspen_automation.dashboard import build_flowsheet_mermaid


def test_build_flowsheet_mermaid_nodes_edges_and_terminals():
    spec = {
        "blocks": [
            {"name": "RX", "type": "RSTOIC"},
            {"name": "SEP", "type": "SEP"},
        ],
        "flowsheet": [
            {"block": "RX", "inputs": ["FEED", "RECYCLE"], "outputs": ["RXOUT"]},
            {"block": "SEP", "inputs": ["RXOUT"], "outputs": ["PRODUCT", "RECYCLE"]},
        ],
    }
    mermaid = build_flowsheet_mermaid(spec)

    assert mermaid.startswith("graph LR")
    # block nodes with type labels
    assert 'RX["RX (RSTOIC)"]' in mermaid
    assert 'SEP["SEP (SEP)"]' in mermaid
    # external feed becomes a terminal feeding RX
    assert 'feed_FEED(["FEED"]) -->|FEED| RX' in mermaid
    # internal stream RX -> SEP
    assert "RX -->|RXOUT| SEP" in mermaid
    # product has no consumer -> terminal out node
    assert 'SEP -->|PRODUCT| out_PRODUCT(["PRODUCT"])' in mermaid
    # recycle goes back into RX
    assert "SEP -->|RECYCLE| RX" in mermaid


def test_build_flowsheet_mermaid_empty_spec():
    assert build_flowsheet_mermaid({}) == "graph LR"
```

- [ ] **Step 2: Run to verify it fails**

Run: `pixi run python -m pytest tests/unit/test_dashboard.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aspen_automation.dashboard'`.

- [ ] **Step 3: Create the module with the builder**

Create `aspen_automation/dashboard.py`:

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `pixi run python -m pytest tests/unit/test_dashboard.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add aspen_automation/dashboard.py tests/unit/test_dashboard.py
git commit -m "feat(dashboard): flowsheet Mermaid builder from spec connectivity"
```

---

## Task 3: Data collection from run artifacts

**Files:**
- Modify: `aspen_automation/dashboard.py`
- Test: `tests/unit/test_dashboard.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_dashboard.py`:

```python
import json as _json

from aspen_automation.dashboard import collect_dashboard_data


def _seed_results_dir(tmp_path):
    (tmp_path / "kpis.json").write_text(
        _json.dumps({"methanol_tpd": 9812.0, "synthesis_loop": {"co_conversion_fraction": 0.34}}),
        encoding="utf-8",
    )
    (tmp_path / "acceptance.json").write_text(_json.dumps({"passed": True}), encoding="utf-8")
    (tmp_path / "streams.csv").write_text(
        "stream_name,temperature,CH4_mole_frac,H2_mole_frac\nFEED,25,0.9,0.1\n",
        encoding="utf-8",
    )
    return tmp_path


def test_collect_dashboard_data_reads_artifacts(tmp_path):
    results_dir = _seed_results_dir(tmp_path)
    spec = {"metadata": {"title": "T"}, "components": [{"id": "CH4"}], "flowsheet": [], "blocks": []}

    data = collect_dashboard_data(results_dir, spec)

    assert data["kpis"]["methanol_tpd"] == 9812.0
    assert data["acceptance"]["passed"] is True
    assert list(data["streams"]["stream_name"]) == ["FEED"]
    assert data["metadata"]["title"] == "T"
    assert data["flowsheet_mermaid"].startswith("graph LR")


def test_collect_dashboard_data_missing_files_are_empty(tmp_path):
    data = collect_dashboard_data(tmp_path, None)

    assert data["kpis"] == {}
    assert data["acceptance"] == {}
    assert data["streams"].empty
    assert data["flowsheet_mermaid"] == ""
```

- [ ] **Step 2: Run to verify it fails**

Run: `pixi run python -m pytest tests/unit/test_dashboard.py -q`
Expected: FAIL — `ImportError: cannot import name 'collect_dashboard_data'`.

- [ ] **Step 3: Implement the collector**

Append to `aspen_automation/dashboard.py`:

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `pixi run python -m pytest tests/unit/test_dashboard.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add aspen_automation/dashboard.py tests/unit/test_dashboard.py
git commit -m "feat(dashboard): collect run artifacts into dashboard data"
```

---

## Task 4: KPI gauge + synthesis-loop figures

**Files:**
- Modify: `aspen_automation/dashboard.py`
- Test: `tests/unit/test_dashboard.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_dashboard.py`:

```python
from aspen_automation.dashboard import figure_kpis, figure_synthesis_loop


def test_figure_kpis_is_gauge_with_methanol_value():
    data = {"kpis": {"methanol_tpd": 9812.0}}
    fig = figure_kpis(data)
    assert fig.data[0].type == "indicator"
    assert fig.data[0].value == 9812.0
    assert fig.data[0].gauge.axis.range == (0, 10000)


def test_figure_synthesis_loop_bar_labels():
    data = {"kpis": {"synthesis_loop": {
        "co_conversion_fraction": 0.34,
        "co2_conversion_fraction": 0.12,
        "h2_consumption_fraction": 0.40,
    }}}
    fig = figure_synthesis_loop(data)
    assert fig.data[0].type == "bar"
    assert list(fig.data[0].x) == ["CO conv", "CO2 conv", "H2 use"]
    assert list(fig.data[0].y) == [0.34, 0.12, 0.40]
```

- [ ] **Step 2: Run to verify it fails**

Run: `pixi run python -m pytest tests/unit/test_dashboard.py -q`
Expected: FAIL — `ImportError: cannot import name 'figure_kpis'`.

- [ ] **Step 3: Implement the figures**

Append to `aspen_automation/dashboard.py`:

```python
def _require_plotly():
    try:
        import plotly.graph_objects as go
    except ImportError as exc:  # pragma: no cover - environment guard
        raise ImportError(
            "plotly is required for dashboard charts. Add it to the pixi env and run "
            "`pixi install` (plotly + nbformat)."
        ) from exc
    return go


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def figure_kpis(data: dict[str, Any]):
    """Gauge of methanol production (TPD) toward the 10k target."""
    go = _require_plotly()
    methanol = _as_float((data.get("kpis") or {}).get("methanol_tpd")) or 0.0
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=methanol,
            title={"text": "Methanol Production (TPD)"},
            gauge={
                "axis": {"range": [0, 10000]},
                "threshold": {"line": {"color": "red", "width": 4}, "thickness": 0.75, "value": 10000},
            },
        )
    )
    fig.update_layout(height=300)
    return fig


def figure_synthesis_loop(data: dict[str, Any]):
    """Grouped conversions for the synthesis loop."""
    go = _require_plotly()
    loop = (data.get("kpis") or {}).get("synthesis_loop") or {}
    labels = ["CO conv", "CO2 conv", "H2 use"]
    values = [
        _as_float(loop.get("co_conversion_fraction")) or 0.0,
        _as_float(loop.get("co2_conversion_fraction")) or 0.0,
        _as_float(loop.get("h2_consumption_fraction")) or 0.0,
    ]
    fig = go.Figure(go.Bar(x=labels, y=values))
    fig.update_layout(title="Synthesis-loop conversions", yaxis_title="fraction", height=350)
    return fig
```

- [ ] **Step 4: Run to verify it passes**

Run: `pixi run python -m pytest tests/unit/test_dashboard.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add aspen_automation/dashboard.py tests/unit/test_dashboard.py
git commit -m "feat(dashboard): KPI gauge and synthesis-loop figures"
```

---

## Task 5: Stream composition + balance figures

**Files:**
- Modify: `aspen_automation/dashboard.py`
- Test: `tests/unit/test_dashboard.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_dashboard.py`:

```python
from aspen_automation.dashboard import (
    figure_balances,
    figure_energy,
    figure_stream_composition,
)


def test_figure_stream_composition_one_trace_per_component():
    data = {"streams": pd.DataFrame({
        "stream_name": ["FEED", "PROD"],
        "CH4_mole_frac": [0.9, 0.0],
        "H2_mole_frac": [0.1, 0.2],
    })}
    fig = figure_stream_composition(data)
    names = sorted(trace.name for trace in fig.data)
    assert names == ["CH4", "H2"]
    assert fig.layout.barmode == "stack"


def test_figure_stream_composition_empty_is_blank_figure():
    fig = figure_stream_composition({"streams": pd.DataFrame()})
    assert len(fig.data) == 0


def test_figure_balances_in_out_traces():
    data = {"material_balance": pd.DataFrame({
        "component": ["CH4", "H2"],
        "input_kmol_hr": [10.0, 5.0],
        "output_kmol_hr": [9.0, 5.0],
    })}
    fig = figure_balances(data)
    names = sorted(trace.name for trace in fig.data)
    assert names == ["in", "out"]


def test_figure_energy_per_block_duty_bars():
    data = {"blocks": pd.DataFrame({
        "block_name": ["B-ATR", "B-COOL"],
        "duty_kw": [1200.0, -800.0],
    })}
    fig = figure_energy(data)
    assert fig.data[0].type == "bar"
    assert list(fig.data[0].x) == ["B-ATR", "B-COOL"]
    assert list(fig.data[0].y) == [1200.0, -800.0]
```

- [ ] **Step 2: Run to verify it fails**

Run: `pixi run python -m pytest tests/unit/test_dashboard.py -q`
Expected: FAIL — `ImportError: cannot import name 'figure_balances'`.

- [ ] **Step 3: Implement the figures**

Append to `aspen_automation/dashboard.py`:

```python
def figure_stream_composition(data: dict[str, Any]):
    """Stacked mole-fraction composition per stream."""
    go = _require_plotly()
    fig = go.Figure()
    df = data.get("streams")
    if isinstance(df, pd.DataFrame) and not df.empty and "stream_name" in df.columns:
        comp_cols = [c for c in df.columns if c.endswith("_mole_frac")]
        for col in comp_cols:
            component = col[: -len("_mole_frac")]
            fig.add_bar(name=component, x=list(df["stream_name"]), y=list(df[col]))
        fig.update_layout(barmode="stack", title="Stream composition (mole frac)", height=400)
    return fig


def figure_balances(data: dict[str, Any]):
    """Material balance: input vs output per component."""
    go = _require_plotly()
    fig = go.Figure()
    df = data.get("material_balance")
    if isinstance(df, pd.DataFrame) and not df.empty and "component" in df.columns:
        if "input_kmol_hr" in df.columns:
            fig.add_bar(name="in", x=list(df["component"]), y=list(df["input_kmol_hr"]))
        if "output_kmol_hr" in df.columns:
            fig.add_bar(name="out", x=list(df["component"]), y=list(df["output_kmol_hr"]))
        fig.update_layout(barmode="group", title="Material balance (kmol/hr)", height=350)
    return fig


def figure_energy(data: dict[str, Any]):
    """Per-block duty bars (kW) from the blocks table."""
    go = _require_plotly()
    fig = go.Figure()
    df = data.get("blocks")
    if isinstance(df, pd.DataFrame) and not df.empty and {"block_name", "duty_kw"} <= set(df.columns):
        fig.add_bar(name="duty_kw", x=list(df["block_name"]), y=list(df["duty_kw"]))
        fig.update_layout(title="Per-block duty (kW)", yaxis_title="kW", height=350)
    return fig
```

- [ ] **Step 4: Run to verify it passes**

Run: `pixi run python -m pytest tests/unit/test_dashboard.py -q`
Expected: PASS (10 passed).

- [ ] **Step 5: Commit**

```bash
git add aspen_automation/dashboard.py tests/unit/test_dashboard.py
git commit -m "feat(dashboard): stream composition and balance figures"
```

---

## Task 6: Mermaid inline renderer + KPI cards HTML

**Files:**
- Modify: `aspen_automation/dashboard.py`
- Test: `tests/unit/test_dashboard.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_dashboard.py`:

```python
from aspen_automation.dashboard import render_mermaid_html, kpi_cards_html


def test_render_mermaid_html_wraps_diagram_in_iframe():
    html = render_mermaid_html("graph LR\n A-->B")
    assert "<iframe" in html.data
    assert "srcdoc=" in html.data
    assert "graph LR" in html.data
    assert "mermaid" in html.data


def test_kpi_cards_html_contains_values():
    data = {"kpis": {
                "methanol_tpd": 9812,
                "convergence_status": "converged",
                "product_stream": "MEOH",
                "synthesis_loop": {
                    "inlet_stoichiometric_number": 1.97,
                    "inlet_ch4_mole_frac": 0.02,
                    "inlet_co2_mole_frac": 0.05,
                },
            },
            "acceptance": {"passed": True}}
    html = kpi_cards_html(data)
    assert "9812" in html
    assert "MEOH" in html
    assert "PASS" in html
    # synthesis-loop SN + recycle surfaced as cards (with SN target band noted)
    assert "1.97" in html
    assert "1.8" in html and "2.2" in html
    assert "0.02" in html
```

- [ ] **Step 2: Run to verify it fails**

Run: `pixi run python -m pytest tests/unit/test_dashboard.py -q`
Expected: FAIL — `ImportError: cannot import name 'render_mermaid_html'`.

- [ ] **Step 3: Implement renderer and cards**

Append to `aspen_automation/dashboard.py`:

```python
import html as _html


def render_mermaid_html(mermaid_text: str, mermaid_js_url: str = DEFAULT_MERMAID_JS, height: int = 480):
    """Return an IPython HTML iframe that renders the Mermaid diagram.

    The diagram is placed inside an ``<iframe srcdoc>`` so the Mermaid module
    script executes even in renderers (e.g. VS Code notebooks) that strip
    scripts from top-level HTML outputs.
    """
    from IPython.display import HTML

    srcdoc = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        "<style>body{margin:0;font-family:Arial,sans-serif;}</style></head><body>"
        '<pre class="mermaid">' + _html.escape(mermaid_text) + "</pre>"
        '<script type="module">'
        f'import mermaid from "{mermaid_js_url}";'
        "mermaid.initialize({startOnLoad:true});"
        "</script></body></html>"
    )
    iframe = (
        f'<iframe srcdoc="{_html.escape(srcdoc, quote=True)}" '
        f'style="width:100%;height:{height}px;border:0;"></iframe>'
    )
    return HTML(iframe)


def kpi_cards_html(data: dict[str, Any]) -> str:
    """Compact HTML KPI card row."""
    kpis = data.get("kpis") or {}
    loop = kpis.get("synthesis_loop") or {}
    passed = (data.get("acceptance") or {}).get("passed")
    acceptance = "PASS" if passed else ("FAIL" if passed is not None else "n/a")
    cards = [
        ("Convergence", kpis.get("convergence_status", "unknown")),
        ("Product stream", kpis.get("product_stream", "n/a")),
        ("Methanol TPD", kpis.get("methanol_tpd", "n/a")),
        ("Total product TPD", kpis.get("product_total_tpd", "n/a")),
        ("Acceptance", acceptance),
        ("Stoich number SN (target 1.8–2.2)", loop.get("inlet_stoichiometric_number", "n/a")),
        ("Recycle CH4 mole frac", loop.get("inlet_ch4_mole_frac", "n/a")),
        ("Recycle CO2 mole frac", loop.get("inlet_co2_mole_frac", "n/a")),
    ]
    cell = (
        '<div style="flex:1;min-width:140px;border:1px solid #ddd;border-radius:8px;'
        'padding:10px;margin:4px;background:#f8fafc;">'
        '<div style="font-size:12px;color:#64748b;">{label}</div>'
        '<div style="font-size:18px;font-weight:700;color:#0f172a;">{value}</div></div>'
    )
    body = "".join(cell.format(label=label, value=value) for label, value in cards)
    return f'<div style="display:flex;flex-wrap:wrap;">{body}</div>'
```

- [ ] **Step 4: Run to verify it passes**

Run: `pixi run python -m pytest tests/unit/test_dashboard.py -q`
Expected: PASS (12 passed).

- [ ] **Step 5: Commit**

```bash
git add aspen_automation/dashboard.py tests/unit/test_dashboard.py
git commit -m "feat(dashboard): Mermaid iframe renderer and KPI cards"
```

---

## Task 7: Standalone HTML export (`save_dashboard_html` + `build_dashboard_html`)

**Files:**
- Modify: `aspen_automation/dashboard.py`
- Test: `tests/unit/test_dashboard.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_dashboard.py`:

```python
from aspen_automation.dashboard import build_dashboard_html, save_dashboard_html


def test_build_dashboard_html_contains_sections():
    data = {
        "metadata": {"title": "Methanol Plant"},
        "kpis": {"methanol_tpd": 9812, "product_stream": "MEOH"},
        "acceptance": {"passed": True},
        "streams": pd.DataFrame({"stream_name": ["FEED"], "CH4_mole_frac": [1.0]}),
        "material_balance": pd.DataFrame({"component": ["CH4"], "input_kmol_hr": [1.0], "output_kmol_hr": [1.0]}),
        "flowsheet_mermaid": "graph LR\n A-->B",
    }
    html = build_dashboard_html(data, [figure_kpis(data)])
    assert "Methanol Plant" in html
    assert "graph LR" in html
    assert "plotly" in html.lower()
    assert "MEOH" in html


def test_save_dashboard_html_writes_file(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    _seed_results_dir(results_dir)
    out = save_dashboard_html(results_dir, tmp_path, spec={"metadata": {"title": "X"}, "components": [{"id": "CH4"}]})
    assert out == tmp_path / "dashboard.html"
    assert out.is_file()
    assert "X" in out.read_text(encoding="utf-8")
```

Note: `_seed_results_dir` is defined earlier in the test file (Task 3); it writes files
into the directory it is given, so the `results` subdir must exist before seeding.

- [ ] **Step 2: Run to verify it fails**

Run: `pixi run python -m pytest tests/unit/test_dashboard.py -q`
Expected: FAIL — `ImportError: cannot import name 'build_dashboard_html'`.

- [ ] **Step 3: Implement export**

Append to `aspen_automation/dashboard.py`:

```python
def _all_figures(data: dict[str, Any]) -> list:
    return [
        figure_kpis(data),
        figure_synthesis_loop(data),
        figure_stream_composition(data),
        figure_balances(data),
        figure_energy(data),
    ]


def build_dashboard_html(
    data: dict[str, Any],
    figures: list,
    mermaid_js_url: str = DEFAULT_MERMAID_JS,
) -> str:
    """Assemble a standalone HTML dashboard string (cards + flowsheet + charts)."""
    title = (data.get("metadata") or {}).get("title", "Aspen Run Dashboard")
    cards = kpi_cards_html(data)
    mermaid = data.get("flowsheet_mermaid") or ""
    mermaid_block = ""
    if mermaid:
        mermaid_block = (
            "<h2>Process flowsheet</h2>"
            '<pre class="mermaid">' + _html.escape(mermaid) + "</pre>"
            '<script type="module">'
            f'import mermaid from "{mermaid_js_url}";'
            "mermaid.initialize({startOnLoad:true});"
            "</script>"
        )

    fig_blocks = []
    for index, fig in enumerate(figures):
        fig_blocks.append(
            fig.to_html(full_html=False, include_plotlyjs="cdn" if index == 0 else False)
        )

    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{_html.escape(str(title))}</title>"
        "<style>body{font-family:Arial,sans-serif;margin:24px;color:#0f172a;}</style>"
        "</head><body>"
        f"<h1>{_html.escape(str(title))}</h1>"
        f"{cards}{mermaid_block}"
        "<h2>Results</h2>"
        + "".join(fig_blocks)
        + "</body></html>"
    )


def save_dashboard_html(
    results_dir: str | Path,
    run_dir: str | Path,
    spec: dict[str, Any] | None = None,
    mermaid_js_url: str = DEFAULT_MERMAID_JS,
) -> Path:
    """Write a standalone ``dashboard.html`` into ``run_dir`` and return its path."""
    data = collect_dashboard_data(results_dir, spec)
    html = build_dashboard_html(data, _all_figures(data), mermaid_js_url)
    out = Path(run_dir) / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    return out
```

- [ ] **Step 4: Run to verify it passes**

Run: `pixi run python -m pytest tests/unit/test_dashboard.py -q`
Expected: PASS (14 passed).

- [ ] **Step 5: Commit**

```bash
git add aspen_automation/dashboard.py tests/unit/test_dashboard.py
git commit -m "feat(dashboard): standalone HTML export"
```

---

## Task 8: `display_dashboard` orchestrator + package export

**Files:**
- Modify: `aspen_automation/dashboard.py`
- Modify: `aspen_automation/__init__.py`
- Test: `tests/unit/test_dashboard.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_dashboard.py`:

```python
import aspen_automation


def test_dashboard_symbols_exported():
    assert hasattr(aspen_automation, "display_dashboard")
    assert hasattr(aspen_automation, "collect_dashboard_data")
    assert hasattr(aspen_automation, "build_flowsheet_mermaid")
    assert hasattr(aspen_automation, "save_dashboard_html")
```

- [ ] **Step 2: Run to verify it fails**

Run: `pixi run python -m pytest tests/unit/test_dashboard.py::test_dashboard_symbols_exported -q`
Expected: FAIL — `AssertionError` (attributes missing).

- [ ] **Step 3: Implement orchestrator**

Append to `aspen_automation/dashboard.py`:

```python
def display_dashboard(
    result: Any,
    spec: dict[str, Any] | None = None,
    *,
    save_html: bool = False,
    mermaid_js_url: str = DEFAULT_MERMAID_JS,
) -> None:
    """Render the interactive dashboard inline in a notebook for one run result."""
    from IPython.display import HTML, Markdown, display

    layout = getattr(result, "layout", None)
    if layout is None:
        print(f"No run layout available for {getattr(result, 'process_name', 'run')}; cannot build dashboard.")
        return

    if spec is None:
        try:
            spec = load_process_spec(result.process_dir)
        except Exception as exc:  # noqa: BLE001 - spec is optional for the flowsheet
            print(f"Could not load spec for flowsheet ({exc}); rendering without it.")
            spec = None

    data = collect_dashboard_data(layout.results_dir, spec)
    title = (data.get("metadata") or {}).get("title") or getattr(result, "process_name", "Run")

    display(Markdown(f"# Dashboard: {title}"))
    display(HTML(kpi_cards_html(data)))

    if data.get("flowsheet_mermaid"):
        display(Markdown("## Process flowsheet"))
        display(render_mermaid_html(data["flowsheet_mermaid"], mermaid_js_url))

    display(Markdown("## Results"))
    for fig in _all_figures(data):
        fig.show()

    streams = data.get("streams")
    if isinstance(streams, pd.DataFrame) and not streams.empty:
        display(Markdown("## Streams"))
        display(streams)

    for label, key in (("Material balance", "material_balance"), ("Energy balance", "energy_balance")):
        table = data.get(key)
        if isinstance(table, pd.DataFrame) and not table.empty:
            display(Markdown(f"## {label}"))
            display(table)

    if save_html:
        out = save_dashboard_html(layout.results_dir, layout.run_dir, spec, mermaid_js_url)
        print(f"Saved standalone dashboard: {out}")
```

- [ ] **Step 4: Export from the package**

In `aspen_automation/__init__.py`, add an import next to the other submodule imports
(e.g. right after `from .reporter import generate_reports`):

```python
from .dashboard import (
    build_flowsheet_mermaid,
    collect_dashboard_data,
    display_dashboard,
    save_dashboard_html,
)
```

And add these names to the `__all__` list (next to `"generate_reports"`):

```python
    "build_flowsheet_mermaid",
    "collect_dashboard_data",
    "display_dashboard",
    "save_dashboard_html",
```

- [ ] **Step 5: Run to verify it passes**

Run: `pixi run python -m pytest tests/unit/test_dashboard.py -q`
Expected: PASS (15 passed).

- [ ] **Step 6: Commit**

```bash
git add aspen_automation/dashboard.py aspen_automation/__init__.py tests/unit/test_dashboard.py
git commit -m "feat(dashboard): display_dashboard orchestrator and package exports"
```

---

## Task 9: Wire the dashboard into the notebooks

**Files:**
- Modify: `notebooks/methanol_example_runner.ipynb`
- Modify: `notebooks/process_library_runner.ipynb`

- [ ] **Step 1: Insert the dashboard code cell (methanol notebook)**

Use the `NotebookEdit` tool. Insert a **code** cell after the cell with id
`gate2-diagnostics-evidence` in `notebooks/methanol_example_runner.ipynb`:

```python
from aspen_automation import display_dashboard

if not process_results:
    print("No process runs available for the dashboard. Run Gate 2 first.")
else:
    for result in process_results:
        if result.succeeded:
            display_dashboard(result)
        else:
            print(f"Skipping dashboard for {result.process_name}: status={result.status!r}")
```

- [ ] **Step 2: Insert the section header (methanol notebook)**

Use `NotebookEdit` again, insert a **markdown** cell after the cell with id
`gate2-diagnostics-evidence` (this places it *before* the code cell from Step 1):

```markdown
## 11.5 Interactive run dashboard

Renders a Plotly + Mermaid dashboard (flowsheet, KPI gauge, synthesis-loop diagnostics,
stream composition, material/energy balance) from each run's saved `results/` artifacts.
This reads persisted artifacts, so it does **not** require Aspen Plus to be running.
```

- [ ] **Step 3: Repeat for the process-library notebook**

Open `notebooks/process_library_runner.ipynb` with the `Read` tool, find the Gate 2
diagnostics/evidence cell (the cell that builds `diagnostic_rows` from
`process_results`). Insert the **same** code cell and markdown header after it using the
same two-step `NotebookEdit` insert approach. Use the actual cell id from that notebook
as the anchor.

- [ ] **Step 4: Sanity-check the notebooks parse**

Run: `pixi run python -c "import nbformat; [nbformat.read(p, as_version=4) for p in ['notebooks/methanol_example_runner.ipynb','notebooks/process_library_runner.ipynb']]; print('ok')"`
Expected: prints `ok` (both notebooks are valid JSON/nbformat).

- [ ] **Step 5: Commit**

```bash
git add notebooks/methanol_example_runner.ipynb notebooks/process_library_runner.ipynb
git commit -m "feat(dashboard): add interactive dashboard section to runner notebooks"
```

---

## Task 10: Sync the `.codex` skill bundle mirror

**Files:**
- Create/Modify under `.codex/skills/antigravity-to-aspen-plus/assets/source/`

- [ ] **Step 1: Identify the mirror layout**

Run: `pixi run python -c "from pathlib import Path; base=Path('.codex/skills/antigravity-to-aspen-plus/assets/source'); print('\n'.join(sorted(str(p.relative_to(base)) for p in base.rglob('*') if p.is_file() and ('aspen_automation' in str(p) or 'tests' in str(p) or p.name in {'pixi.toml'} or 'notebooks' in str(p)))))"`
Expected: lists the mirrored `aspen_automation/*.py`, `tests/unit/*.py`, `pixi.toml`, and `notebooks/*.ipynb` files, confirming the mirror mirrors the repo's relative paths.

- [ ] **Step 2: Copy the new/changed files into the mirror**

Run (PowerShell):
```powershell
$base = ".codex/skills/antigravity-to-aspen-plus/assets/source"
Copy-Item aspen_automation/dashboard.py "$base/aspen_automation/dashboard.py" -Force
Copy-Item aspen_automation/__init__.py "$base/aspen_automation/__init__.py" -Force
Copy-Item tests/unit/test_dashboard.py "$base/tests/unit/test_dashboard.py" -Force
Copy-Item pixi.toml "$base/pixi.toml" -Force
Copy-Item notebooks/methanol_example_runner.ipynb "$base/notebooks/methanol_example_runner.ipynb" -Force
Copy-Item notebooks/process_library_runner.ipynb "$base/notebooks/process_library_runner.ipynb" -Force
```
Expected: no errors. (If `$base` lacks a `notebooks` dir or other target dirs, create them with `New-Item -ItemType Directory -Force` first.)

- [ ] **Step 3: Commit**

```bash
git add .codex/skills/antigravity-to-aspen-plus/assets/source
git commit -m "chore(codex): sync dashboard into skill bundle mirror"
```

---

## Task 11: Full unit-test sweep

**Files:** none (verification only)

- [ ] **Step 1: Run the unit suite**

Run: `pixi run python -m pytest tests/unit -q`
Expected: all pass, including the 15 new `test_dashboard.py` tests.

- [ ] **Step 2: Run the focused contract tests (notebook purpose contract may inspect cells)**

Run: `pixi run python -m pytest tests/contract/test_notebook_purpose_contract.py -q`
Expected: PASS. If it asserts on notebook structure and the new cells break it, update the
new markdown/code cells to satisfy the contract (do not weaken the contract test).

- [ ] **Step 3: Final commit if anything changed**

```bash
git add -A
git commit -m "test(dashboard): green unit + notebook-contract suite"
```

---

## Manual verification (after implementation)

Open `notebooks/methanol_example_runner.ipynb` in VS Code, run through Gate 2, then run the
new **11.5** cell. Confirm: KPI cards render, the Mermaid flowsheet renders inside the
iframe, and the four Plotly charts are interactive. If the Mermaid iframe does not render in
this specific VS Code build, switch `mermaid_js_url` to a vendored local copy of
`mermaid.esm.min.mjs` (the renderer and export already accept the override).
