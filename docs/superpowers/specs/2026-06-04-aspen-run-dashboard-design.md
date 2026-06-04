# Aspen Run Dashboard — Design

**Date:** 2026-06-04
**Status:** Approved (design); pending implementation plan
**Topic:** Interactive in-notebook dashboard for process flowsheet + run results

## Problem

A batch-first run (`run_process_batch_first`) writes a `results/` directory full of
artifacts (`streams.csv`, `blocks.csv`, `material_balance.csv`, `energy_balance.csv`,
`kpis.json`, `acceptance.json`, diagnostics JSONs) and a single static
`run_summary.html` from `aspen_automation/reporter.py` that is only a KPI table plus
the top-10 streams and top-10 blocks. There is **no flowsheet diagram and no charts**.
Users need to *visualize* the process flowsheet and the run results without reading raw
CSV/JSON.

## Goal

An **interactive, in-notebook dashboard** rendered next to the run cells that shows:

1. KPI cards + a methanol-TPD gauge toward the 10k TPD target
2. Synthesis-loop (kinetic) diagnostics
3. Stream composition charts + a streams table
4. Material & energy balance charts/tables
5. A **process flowsheet diagram** derived from the spec connectivity

Decisions locked during brainstorming:

- **Delivery:** interactive in-notebook (not a server, not primarily a file).
- **Charts:** **Plotly** figures rendered via their native notebook mimetype (reliable in
  the user's VS Code + JupyterLab).
- **Flowsheet:** **Mermaid** (`graph LR`) rendered inline via an `<iframe srcdoc>` so the
  JS executes inside VS Code notebook outputs.

## Non-goals (YAGNI)

- No web server / multi-run browser (no Streamlit/Dash).
- No static image export (no kaleido).
- `dashboard.html` static export is an **optional** `save_html` flag, not core.
- No new visual beyond the five groups above.

## Architecture

New module `aspen_automation/dashboard.py`. `reporter.py` is unchanged (it remains the
static file-writer). The module separates **data gathering** (pure, testable, no
rendering) from **rendering** (Plotly/Mermaid/IPython).

| Function | Responsibility | Testable without browser? |
|---|---|---|
| `collect_dashboard_data(result, spec) -> dict` | Read `kpis.json`, `streams.csv`, `blocks.csv`, `material_balance.csv`, `energy_balance.csv`, `acceptance.json` from `result.layout.results_dir`; attach flowsheet connectivity from `spec`. Missing artifacts degrade to empty structures, never raise. | ✅ fixture results dir |
| `build_flowsheet_mermaid(spec) -> str` | Derive a Mermaid `graph LR` string from `spec["flowsheet"]` (`{block, inputs[], outputs[]}`), `spec["blocks"]` (types), and `spec["streams"]`. Streams with no producing block → feed terminals; streams with no consuming block → product/purge terminals. | ✅ pure string |
| `figure_kpis(data)`, `figure_synthesis_loop(data)`, `figure_stream_composition(data)`, `figure_balances(data)` | One builder per visual group; each returns a `plotly.graph_objects.Figure`. No display side effects. | ✅ assert traces |
| `display_dashboard(result, spec=None, save_html=False, mermaid_js_url=DEFAULT)` | Orchestrate: gather data → render Mermaid flowsheet inline → show Plotly figures + tables. If `spec is None`, load it from `result.process_dir`. If `save_html`, also write `dashboard.html` to `result.layout.run_dir`. | rendering (manual verify) |

The dashboard reads **already-persisted artifacts**, so it does **not** require Aspen
Plus running — any past run directory can be rendered.

## Data sources (per visual group)

All paths are under `result.layout.results_dir` unless noted.

1. **KPI cards + methanol gauge** — `kpis.json` (`convergence_status`, `product_stream`,
   `product_total_tpd`, `methanol_tpd`) + `acceptance.json` (`passed`). Cards as HTML;
   methanol gauge as a Plotly indicator toward a 10,000 TPD target.
2. **Synthesis-loop diagnostics** — `kpis.json["synthesis_loop"]`
   (`co_conversion_fraction`, `co2_conversion_fraction`, `h2_consumption_fraction`,
   `inlet_stoichiometric_number`, `inlet_ch4_mole_frac`, `inlet_co2_mole_frac`,
   `methanol_formation_kmol_hr`). Grouped conversion bars + an SN indicator with the
   1.8–2.2 target band shaded + recycle CH₄/CO₂ mole fractions.
3. **Stream composition** — `streams.csv`: grouped composition bars for key streams
   (feed, syngas, R-IN, R-OUT, product, recycle, purge where present) + a full streams
   table (T / P / flow). Exact column names verified against a fixture during build.
4. **Material & energy balance** — `material_balance.csv` / `energy_balance.csv`:
   in/out-by-component bars, per-block duty bars, and balance tables; acceptance-vs-target
   comparison from `acceptance.json` where targets exist.
5. **Flowsheet diagram** — Mermaid from spec connectivity (see `build_flowsheet_mermaid`).

## Rendering details

- **Plotly**: figures rendered through the native notebook renderer (`fig.show()` /
  returning figures). Requires `plotly` and `nbformat`.
- **Mermaid**: `IPython.display.HTML` wrapping the diagram in an `<iframe srcdoc="...">`
  that loads `mermaid` (ESM) from `mermaid_js_url` and calls `mermaid.run()`. Default URL
  is the jsDelivr CDN (`mermaid@11`), overridable to a vendored local file for fully
  offline use. The iframe is the same mechanism that lets folium maps run JS inside VS
  Code outputs.

## Dependencies

Add to `pixi.toml [dependencies]`:

- `plotly` — interactive charts.
- `nbformat` — required by Plotly for notebook rendering.

No change to `pyproject.toml` runtime deps (the package core stays pandas/pydantic/pyyaml/
pywin32); the dashboard is a notebook-facing, optional surface. A missing `plotly`/
`nbformat` import raises one clear message instructing the user to `pixi install`.

## Error handling

- Missing result artifact → that section shows a "No <X> data available" placeholder
  (mirrors existing reporter behavior); never raises.
- Missing/`None` spec → flowsheet section is skipped with a note; other sections still
  render.
- Missing `plotly`/`nbformat` → single actionable ImportError-style message.

## Testing (TDD)

`tests/unit/test_dashboard.py`, no Aspen and no browser required:

- `test_build_flowsheet_mermaid`: a small recycle-loop spec (feed → reactor → separator →
  product, with a recycle stream) yields Mermaid text containing the expected block nodes,
  stream-labeled edges, and feed/product terminal nodes.
- `test_collect_dashboard_data`: a temp `results/` dir seeded with fixture
  `kpis.json`/`streams.csv`/`acceptance.json` returns the structured data with correct
  values; absent files yield empty structures without raising.
- `test_figure_builders`: each `figure_*` returns a `plotly.graph_objects.Figure` with the
  expected number/type of traces (smoke level; no rendering).

## Notebook wiring

New section **"## 11.5 Interactive run dashboard"** (after Gate 2 diagnostics) in:

- `notebooks/methanol_example_runner.ipynb`
- `notebooks/process_library_runner.ipynb`

The cell iterates `process_results` and calls `display_dashboard(result)` for each.

## Codex bundle sync

Per the project's bundle-sync rule, after implementation re-mirror into
`.codex/skills/antigravity-to-aspen-plus/assets/source/`:

- the new `aspen_automation/dashboard.py`
- the new `tests/unit/test_dashboard.py`
- the notebook changes
- `pixi.toml` (and `pixi.lock` after `pixi install`)

## Open items to verify during implementation

- Exact `streams.csv` / `material_balance.csv` / `energy_balance.csv` column names from
  the extractor (drive the composition/balance figures from a real fixture).
- That `<iframe srcdoc>` + Mermaid ESM renders in the user's specific VS Code build;
  if blocked, fall back to a vendored Mermaid copy or a Markdown-cell Mermaid block.
