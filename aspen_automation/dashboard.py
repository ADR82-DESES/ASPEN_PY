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
        result = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    return result if isinstance(result, dict) else {}


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
