"""Interactive in-notebook dashboard for process runs.

Pure helpers (``collect_dashboard_data``) have no plotting/IPython dependency.
Chart and render helpers import plotly / matplotlib / IPython lazily so
importing this module never requires them.
"""
from __future__ import annotations

import html as _html
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .process_library import load_process_spec
from .flowsheet_graph import build_flowsheet_mermaid, build_pfd_svg
from .process_sankey import sankey_mass_balance, sankey_energy_balance, stream_styles
from . import figure_style

DEFAULT_MERMAID_JS = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs"


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


def _fig_to_svg_data_uri(fig) -> str:
    import base64
    import io
    import matplotlib.pyplot as plt

    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f'<img style="max-width:100%" src="data:image/svg+xml;base64,{b64}"/>'


def build_dashboard_html(data: dict[str, Any], spec: dict[str, Any] | None = None) -> str:
    """Assemble a standalone HTML dashboard: KPI cards + PFD + Sankeys + nature figures."""
    spec = spec or {}
    title = (data.get("metadata") or {}).get("title", "Aspen Run Dashboard")
    cards = kpi_cards_html(data)

    _flow, _species = stream_styles(data.get("streams"))
    _source, pfd_svg = build_pfd_svg(spec, flow_by_stream=_flow, species_by_stream=_species)
    pfd_block = pfd_svg if "<svg" in pfd_svg else f'<pre class="mermaid">{_html.escape(pfd_svg)}</pre>'

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

    _flow, _species = stream_styles(data.get("streams"))
    _source, pfd_svg = build_pfd_svg(spec, flow_by_stream=_flow, species_by_stream=_species,
                                     out_path=str(figdir / "flowsheet_pfd.svg"))
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


def display_dashboard(
    result: Any,
    spec: dict[str, Any] | None = None,
    *,
    save_html: bool = False,
    save_figures: bool = False,
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

    _flow, _species = stream_styles(data.get("streams"))
    _source, pfd_svg = build_pfd_svg(spec or {}, flow_by_stream=_flow, species_by_stream=_species)
    display(Markdown("## Process flow diagram"))
    if "<svg" in pfd_svg:
        display(HTML(pfd_svg))
    else:
        display(render_mermaid_html(pfd_svg, mermaid_js_url))

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

    streams = data.get("streams")
    if isinstance(streams, pd.DataFrame) and not streams.empty:
        display(Markdown("## Streams"))
        display(streams)

    for label, key in (("Material balance", "material_balance"), ("Energy balance", "energy_balance")):
        table = data.get(key)
        if isinstance(table, pd.DataFrame) and not table.empty:
            display(Markdown(f"## {label}"))
            display(table)

    if save_figures:
        paths = save_dashboard_figures(layout.results_dir, layout.run_dir, spec)
        print(f"Saved {len(paths)} publication figures to {Path(layout.run_dir) / 'figures'}")
    if save_html:
        out = Path(layout.run_dir) / "dashboard.html"
        out.write_text(build_dashboard_html(data, spec), encoding="utf-8")
        print(f"Saved dashboard: {out}")
