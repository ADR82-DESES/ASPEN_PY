# Aspen Dashboard v2 — Publication PFD + Sankey + Nature Figures — Design

**Date:** 2026-06-05
**Status:** Approved (design); pending implementation plan
**Branch:** `feature/run-dashboard`
**Supersedes the figure set of:** `2026-06-04-aspen-run-dashboard-design.md`

## Problem

The v1 dashboard (`aspen_automation/dashboard.py`) renders a Plotly gauge plus
grouped/stacked bar charts and a Mermaid connectivity flowsheet. The user judged this
"extremely poor." They want publication-grade visuals: an advanced **equipment-symbol
process flow diagram**, **Sankey diagrams** for the energy balance and the whole-process
mass balance, and **Nature-journal-style** figures.

## Decisions (locked during brainstorming)

- **Output medium:** BOTH — interactive in-notebook *and* Nature-style static files
  (SVG/PDF) saved to the run directory.
- **PFD:** equipment-symbol PFD via **pyflowsheet** (SVG), with a **Graphviz/Mermaid
  schematic fallback** because pyflowsheet is alpha and self-describes as not print-ready.
- **Mass-balance Sankey:** **whole-process only** (one Sankey; each unit is a node, so
  per-unit balance is read at each node). No per-unit individual Sankeys.
- **Sankey engine:** **Plotly `go.Sankey`** (already installed) for interactive, plus
  **kaleido** for static publication export.
- **Nature styling:** **SciencePlots** `['science','nature','no-latex']` (no LaTeX install
  required on the locked-down machine).
- **Replace** the v1 Plotly gauge/bars; **keep** the v1 KPI cards and reuse
  `collect_dashboard_data`.

## Non-goals (YAGNI)

- No floWeaver. No per-unit individual Sankeys. No web server/Streamlit.
- No new visual beyond: PFD, mass Sankey, energy Sankey, Nature charts, KPI cards.

## Confirmed facts (verified, do not re-derive)

- pyflowsheet (PyPI, alpha): classes for distillation columns, vessels (horizontal/
  vertical), pumps, compressors, heat exchangers, valves, mixers, splitters, stream flags,
  and `BlackBox` (generic). Output is **SVG**. It does **NOT auto-layout** — the caller
  supplies `position=(x,y)` and `size` per unit; pyflowsheet auto-*routes* streams
  (Dijkstra). Minimal API: `Flowsheet(id,title,desc)`, `BlackBox(name,desc,position,size)`,
  `StreamFlag(name,"",position)`, `pfd.addUnits([...])`, `pfd.connect("S01", a["Out"],
  b["In"])`, `pfd.draw(SvgContext("out.svg"))`.
- Block types present in `process_library/methanol/process.yaml`: `MIXER, RGIBBS, HEATER,
  FLASH2, COMPR, RPLUG, FSPLIT, VALVE, RADFRAC` (~18 blocks).
- Spec dict: `flowsheet[]={block, inputs:[stream], outputs:[stream]}`, `blocks[]={name,
  type,...}`, `streams[]`. Real artifacts in `results/`: `streams.csv` columns
  `stream_name, temperature, pressure, mass_flow, mole_flow, <COMP>_mole_frac,
  <COMP>_mass_frac`; `blocks.csv` columns include `block_name, duty_kw, duty_mw,
  net_work_kw, ...`; `material_balance.csv` `component,input_kmol_hr,output_kmol_hr,...`;
  `kpis.json` incl. `synthesis_loop{...}`; `acceptance.json{passed}`.

## Architecture

Three new focused modules + the existing orchestrator. All heavy libs
(matplotlib/scienceplots, plotly, kaleido, pyflowsheet) are **lazy-imported** so importing
`aspen_automation` never requires them; a missing lib raises one actionable message.

### `aspen_automation/process_pfd.py` — equipment-symbol PFD

- `compute_layout(spec) -> dict[str, tuple[int,int]]`: build the directed block graph from
  flowsheet connectivity (block A → block B when a stream is A's output and B's input).
  Assign **layers** by longest-path depth from feed terminals (topological); `x = layer*DX`,
  `y = slot*DY` within a layer (deterministic ordering by block name). Recycle edges are
  allowed (pyflowsheet routes them).
- `block_to_equipment(block_type) -> equipment factory`: MIXER→Mixer, FSPLIT→Splitter,
  RADFRAC/DISTL→DistillationColumn, FLASH2/FLASH3→Vessel, HEATER→HeatExchanger,
  COMPR→Compressor, PUMP→Pump, VALVE→Valve, RGIBBS/RPLUG/RSTOIC/RCSTR→reactor Vessel,
  default→BlackBox. Exact pyflowsheet class names verified in the spike (Task 1).
- `build_pfd_svg(spec, *, out_path=None) -> str`: place units at computed positions, add
  feed/product `StreamFlag`s for terminal streams, `connect()` every stream, `draw()` to an
  SVG string (and file if `out_path`). On ANY pyflowsheet error/ImportError, **fall back**
  to `build_flowsheet_graphviz(spec)` (a styled Graphviz schematic) or the existing
  `build_flowsheet_mermaid(spec)`; return whichever succeeds plus a `source` marker.

### `aspen_automation/process_sankey.py` — Plotly Sankeys

- `sankey_mass_balance(data) -> Figure`: nodes = blocks + one terminal node **per external
  feed stream** and one **per product/purge stream** (distinct nodes, so flows stay
  separable — not a single merged feed/product node). Links = streams; `value = mass_flow`
  (kg/hr) from `streams.csv` joined to flowsheet connectivity (producer→consumer); each feed
  stream links its feed terminal → consuming block, each product/purge links producing block
  → its product terminal. Hover shows stream name + kg/hr. Conservation at each block node
  surfaces imbalance.
- `sankey_energy_balance(data) -> Figure`: nodes = blocks + `Utilities` source + `Heat
  removed` sink + `Work` source. For each block from `blocks.csv`: `duty_kw > 0`
  (endothermic/HEATER) → link `Utilities → block` (value=duty); `duty_kw < 0` → link
  `block → Heat removed` (value=|duty|); `net_work_kw` (COMPR/PUMP) → link `Work → block`.
- Both themed Nature-like (sans-serif, muted palette, white bg) for clean static export.

### `aspen_automation/figure_style.py` — Nature matplotlib figures

- `use_nature_style()`: idempotently apply `plt.style.use(['science','nature','no-latex'])`;
  if SciencePlots is missing, fall back to a built-in rcParams approximation (sans-serif,
  thin spines, 300 dpi) so figures still render.
- `fig_synthesis_loop(data) -> Figure`: Nature-style grouped bars of CO/CO₂/H₂ conversion +
  an SN annotation (target band 1.8–2.2).
- `fig_stream_composition(data) -> Figure`: Nature-style stacked composition bars for key
  streams from `streams.csv`.
- `fig_kpi_summary(data) -> Figure`: Nature-style headline figure (methanol TPD vs 10k
  target, purity, acceptance) — replaces the v1 gauge.

### `aspen_automation/dashboard.py` — orchestrator (modified)

- Reuse `collect_dashboard_data` and `kpi_cards_html` **unchanged**. The mass-link view
  (stream→{src,dst,kg/hr}) and per-unit energy view (block→duty/work) are computed **inside
  the Sankey builders** from the already-collected `streams`/`blocks` DataFrames + spec
  flowsheet, so `collect_dashboard_data` needs no new fields.
- `display_dashboard(result, spec=None, *, save_figures=False, save_html=False)`:
  KPI cards → **PFD (SVG inline)** → **mass Sankey** → **energy Sankey** → **Nature charts**
  → streams/balance tables. Drop the v1 gauge/bar `figure_*` calls.
- `save_dashboard_figures(results_dir, run_dir, spec) -> dict[str,Path]`: write
  `figures/flowsheet_pfd.svg`, `mass_balance_sankey.{svg,pdf}`,
  `energy_balance_sankey.{svg,pdf}`, `synthesis_loop.{svg,pdf}`,
  `stream_composition.{svg,pdf}`, `kpi_summary.{svg,pdf}` (Plotly via kaleido, matplotlib
  via `savefig`, pyflowsheet native SVG). `build_dashboard_html` embeds them.

## Data flow

`result.layout.results_dir` → `collect_dashboard_data` (existing) → builders read
`streams.csv` (mass_flow, composition), `blocks.csv` (duty_kw/net_work_kw), `kpis.json`,
spec flowsheet/blocks → inline display + static export (kaleido / savefig / pyflowsheet).
No new Aspen calls; renders from saved artifacts (no Aspen required).

## Dependencies (pixi)

Add to `pixi.toml`: `matplotlib`, `scienceplots`, `kaleido` under `[dependencies]`
(conda-forge); `pyflowsheet` under `[pypi-dependencies]`. The v1 `plotly`/`nbformat` stay.
A no-LaTeX SciencePlots config avoids needing a TeX install.

## Error handling / graceful degradation

- Missing artifact (streams/blocks/kpis) → that figure shows an empty/"no data" placeholder,
  never raises (consistent with v1).
- Missing pyflowsheet or any PFD render error → Graphviz/Mermaid fallback, with a printed
  note of which renderer was used.
- Missing SciencePlots → built-in rcParams approximation.
- Missing kaleido at export time → skip static Plotly export with a clear note; inline
  interactive still works.

## Testing (TDD; no Aspen, no browser)

- `compute_layout`: small recycle spec → deterministic coords, feed blocks at min x, every
  block placed, no two blocks share a coordinate.
- `block_to_equipment`: each Aspen type maps to the intended class; unknown → BlackBox.
- `build_pfd_svg`: returns an SVG string containing the block names; with pyflowsheet absent
  (monkeypatched ImportError) it returns the fallback and marks `source != "pyflowsheet"`.
- `sankey_mass_balance`: links have correct source/target indices and `value==mass_flow`;
  feed/product terminal nodes exist; returns a Plotly `Figure` with a `sankey` trace.
- `sankey_energy_balance`: endothermic→Utilities link, exothermic→Heat-removed link, work
  link present; signs handled.
- `figure_style`: `use_nature_style()` applies without raising even if SciencePlots missing;
  each `fig_*` returns a matplotlib `Figure` with the expected number of axes/bars.
- `save_dashboard_figures`: writes the expected file set into `figures/` (kaleido + savefig
  paths exercised against a seeded results dir).

## Implementation risk & first step

**Task 1 is a spike**: add the deps in pixi, confirm `pyflowsheet`, `scienceplots`, and
`kaleido` import and that a trivial pyflowsheet PFD renders to SVG and a trivial Plotly
Sankey exports via kaleido. Pin the exact pyflowsheet equipment class names from the
installed version. If pyflowsheet cannot install or render in the pixi/win-64 environment,
the Graphviz fallback becomes the primary PFD and the spec's PFD task switches to it (the
rest of the design is unaffected).

## Module-size note

`dashboard.py` is already ~375 lines; the PFD, Sankey, and Nature-figure code live in their
own modules (above) rather than growing `dashboard.py` further. `dashboard.py` keeps only
orchestration + export wiring. v1 `figure_kpis/figure_synthesis_loop/figure_stream_
composition/figure_balances/figure_energy` are removed (replaced); their tests are updated
or removed accordingly.
