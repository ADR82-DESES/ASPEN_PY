---
name: antigravity-to-aspen-plus
description: Build, run, diagnose, and replicate Aspen Plus process simulations from an Antigravity/process-library specification. Use when Codex needs to create or port the schema-first Aspen automation stack: process.yaml specs, INP generation, Aspen batch translation to BKP, COM BKP loading/extraction, notebook-only execution, diagnostics, result CSV/JSON export, and live Aspen troubleshooting.
---

# Antigravity To Aspen Plus

Use the repo's schema-first, batch-first path. The normal workflow is:

`process.yaml -> generate_inp(...) -> run_aspen_batch(...) -> .his/.bkp gate -> InitFromArchive2 COM load -> extract_results(...) -> notebook diagnostics`

Prefer this batch-first capsule path over raw COM block creation. The COM block builder is a legacy/debug fallback, not the primary way to build live cases.

## Precedence

If this skill conflicts with generic Aspen Plus rules, follow this skill for workflow, file selection, and implementation patterns. Use generic Aspen COM guidance only when this skill is silent.

## Replication Contract

This skill is self-contained. It includes a working source snapshot under `assets/source/`:

- `assets/source/aspen_automation/`: the batch-first Aspen automation package.
- `assets/source/notebooks/process_library_runner.ipynb`: the notebook-only workflow.
- `assets/source/process_library/methanol/process.yaml`: the working methanol process example.
- `assets/source/tests/`: unit, contract, and live integration test sources.
- `assets/source/pyproject.toml` and `assets/source/pixi.toml`: environment references.
- `scripts/bootstrap_aspen_automation.py`: non-destructive copy script for fresh projects.

When this skill is copied into a new project, install the bundled source before attempting a live Aspen run:

```powershell
python .codex\skills\antigravity-to-aspen-plus\scripts\bootstrap_aspen_automation.py --target .
```

By default the bootstrap script merges directories and skips existing files with different contents. Use `--dry-run` to inspect planned copies and `--force` only when intentionally replacing project files.

After bootstrapping, check whether the project has the required architecture. If files or APIs are missing because the target project is intentionally different, adapt from `assets/source/` rather than reconstructing from prose.

Required project shape:

- `process_library/<name>/process.yaml`: canonical process spec.
- `notebooks/process_library_runner.ipynb`: primary user workflow.
- `aspen_automation/schema.py`: typed schema/validation for components, properties, streams, flowsheet, blocks, reaction sets, kinetic models, and defaults.
- `aspen_automation/inp_generator.py`: Aspen batch-compatible INP emitter.
- `aspen_automation/batch_engine.py`: runs Aspen batch and parses `.his`.
- `aspen_automation/process_library.py`: high-level runners, especially `run_process_batch_first(...)` and `load_bkp_and_extract_results(...)`.
- `aspen_automation/session.py`: Aspen COM connection and `InitFromArchive2` support.
- `aspen_automation/extractor.py`: stream/block/material/energy/KPI extraction.
- `aspen_automation/capsule_context.py`: process ancestry, Aspen path, COM identity, AppsAnywhere/Cloudpaging markers, localization assembly visibility, and optional diagnostics.
- `aspen_automation/process_results_analysis.py`: CSV-based analysis helpers.
- Tests covering schema, INP generation, `.his` parsing, batch-first orchestration, notebook contract, context probing, and process-library behavior.

If the target project does not have this stack, install or port the bundled source in this order:

1. Schema and validation: `schema.py`, spec loading, and `validate_spec(...)`.
2. INP generation: `generate_inp(...)` plus translator-focused unit tests.
3. Batch engine: `run_aspen_batch(...)`, `.his` parsing, and `AspenBatchResult.succeeded`.
4. COM session/load layer: Aspen dispatch, `InitFromArchive2`, visibility/dialog settings, and convergence checks.
5. Extractor: streams, blocks, material balance, energy balance, KPIs, and report writing.
6. Batch-first orchestration: `run_process_batch_first(...)` and `load_bkp_and_extract_results(...)`.
7. Context evidence: `context_probe.json` collection with optional diagnostics marked `skipped` when unavailable.
8. Notebook: Gate 1, Gate 2, diagnostics, summary, and CSV analysis cells.
9. Tests and live gates.

Portable user workflow:

1. Launch Aspen Plus from AppsAnywhere/Porticada or the local Aspen installation.
2. Open `notebooks/process_library_runner.ipynb`.
3. Restart the kernel.
4. Run cells top-to-bottom.
5. Inspect Gate 1 batch translation, Gate 2 BKP COM load/extraction, diagnostics, result CSVs, and `live_aspen_summary.json`.

## Process Spec Rules

Translate Antigravity output into the process-library schema:

- Use `metadata`, `components`, `properties.method`, `flowsheet`, `streams`, `blocks`, optional `chemistry`, optional `reaction_sets`, optional `kinetic_models`, and optional `process_defaults`.
- Put thermodynamics only in `properties.method`.
- Put stream definitions in `streams`.
- Put unit operations in `blocks`.
- Put connections in `flowsheet`.
- Use `process_defaults.product_stream` for production KPIs; never infer production from the largest terminal stream.
- Keep `process_library/<name>/process.yaml` canonical. Allow `spec_path` only as a debug override and fail if it conflicts with the canonical process path.

Validate before Aspen:

```python
from aspen_automation import load_spec, validate_spec

spec = load_spec("process_library/methanol/process.yaml")
validate_spec(spec)
```

Fix undefined streams/blocks, duplicate names, unsupported block types, invalid reaction links, and compositions that do not sum to 1.0 before generating INP.

## Batch-First Gates

Gate 1 is the Aspen batch translator gate:

- Generate INP with `generate_inp(...)`.
- Run Aspen batch with `run_aspen_batch(...)`.
- Treat `.bkp` existence as insufficient.
- Success requires no timeout/error, archive path present, and `history_diagnostics.status == "converged"` or equivalently no terminal/severe/input-translation errors.
- If `.his` reports failed input translation, stop and fix INP generation/spec syntax before touching COM.

Gate 2 is the BKP COM load/extraction gate:

- Load the batch-created `.bkp` with `InitFromArchive2`.
- Extract streams, blocks, material balance, energy balance, KPIs, diagnostics, and reports.
- Do not call `run_simulation_session(..., build_mode="auto")`.
- Do not re-enter the COM block builder.

Gate 3 is process credibility:

- Require convergence and readable result tables.
- For methanol or kinetic processes, require nonzero expected product formation before nameplate targets.
- Display acceptance targets by default, but do not enforce them until reactor/recycle/product KPIs are stable.

## Primary APIs

Use these imports for new work:

```python
from aspen_automation import (
    build_codex_results_markdown,
    generate_inp,
    load_result_artifact_tables,
    load_spec,
    run_aspen_batch,
    run_methanol_tuning_campaign,
    run_process_batch_first,
    validate_spec,
)
```

Notebook/default live run:

```python
from pathlib import Path
from aspen_automation import run_process_batch_first

result = run_process_batch_first(
    Path("process_library/methanol"),
    Path("process_runs/batch_first_capsule"),
    visible=True,
    enforce_acceptance_targets=False,
    timeout_seconds=1800,
    batch_timeout_seconds=1800,
    report_format="html",
)

if not result.succeeded:
    raise RuntimeError(result.error or result.status)
```

Gate 1 only:

```python
from pathlib import Path
from aspen_automation import generate_inp, load_spec, run_aspen_batch

process_dir = Path("process_library/methanol")
spec = load_spec(process_dir / "process.yaml")
inp_path = Path("process_runs/gate1/methanol_generated.inp")
generate_inp(spec, output_path=inp_path)
batch = run_aspen_batch(inp_path, inp_path.parent / "batch", run_id="methanol", timeout_seconds=1800)

if not batch.succeeded:
    raise RuntimeError(batch.history_diagnostics)
```

## Notebook Contract

`notebooks/process_library_runner.ipynb` should be the normal user surface. It must contain:

- Imports for `run_process_batch_first`, `generate_inp`, `load_spec`, `run_aspen_batch`, `load_result_artifact_tables`, and `build_codex_results_markdown`.
- Default `enforce_acceptance_targets=False`.
- A Gate 1 cell before full execution that generates INP, runs batch, displays `.his` status, archive path, stdout/stderr paths, and first blocking history messages.
- A Gate 2 execution cell that calls `run_process_batch_first(...)`.
- Diagnostics cells showing `context_probe.json`, `build_diagnostics.json`, `simulation_diagnostics.json`, `acceptance.json`, and `live_aspen_summary.json`.
- CSV-based analysis using `load_result_artifact_tables(...)` and `build_codex_results_markdown(...)`.
- Optional tuning cells only after the base run is readable.

Do not make the user run terminal commands for the standard workflow.

## Context Evidence

For AppsAnywhere/Cloudpaging deployments, prove the worker is inside the virtualized Aspen context. The run should write `context_probe.json` containing:

- Current process ancestry.
- Resolved `aspen.exe` or Aspen Plus executable path.
- Aspen COM identity/version details when available.
- AppsAnywhere/Cloudpaging package markers.
- Whether `AspenTech.AspenPlus.Localization` is visible from that worker context.
- Optional Fusion/.NET and ProcMon diagnostics.

Fusion and ProcMon are best-effort only. Missing elevation, unavailable tools, or disabled logging must be recorded as `skipped`, never treated as normal run failures.

## INP Generation Rules

The generated INP must be accepted by Aspen's real batch translator, not just by local tests.

Important patterns:

- Emit real Aspen-supported block types and parameter names.
- Keep RPLUG integer parameters like `NPOINT` as integers.
- For kinetic RPLUG/POWERLAW models, attach reactions through `REACTIONS <set> POWERLAW` and the block `REACTIONS` parameter.
- Do not duplicate kinetic reactions into unsupported standalone `CHEMISTRY` paragraphs if Aspen expects them in the reaction set.
- Do not include methanation in a methanol-selective synthesis reactor unless the user explicitly requests it.
- For early infrastructure validation, use screening kinetics and label them as uncalibrated until plant/vendor catalyst data are available.

## Methanol-Specific Lessons

For ATR-like methanol process work:

- `B-SYN` should be methanol-selective, typically RPLUG or another kinetic reactor, not unconstrained RGIBBS.
- Track both total product TPD and component `CH3OH` TPD from `process_defaults.product_stream`, normally `MEOH-PRO`.
- Report synthesis-loop diagnostics: CO conversion, CO2 conversion, H2 consumption, methanol formation, methane change, recycle/feed stoichiometric number, CH4 mole fraction, and CO2 mole fraction.
- Tune in this order: prove methanol formation, tune reactor kinetic scale/sizing, tune purge/recycle losses, then tune ATR steam/O2 to move SN toward about 2.0, then improve purification.
- Treat 10k TPD/nameplate targets as late-stage acceptance targets, not first live-run blockers.

Reactor-only kinetic sanity diagnostic:

```python
from aspen_automation import (
    build_reactor_only_kinetic_sweep_specs,
    diagnose_kinetic_sweep_results,
)
```

Use this before touching ATR or distillation when full-loop methanol is near zero. Sweep pre-exponential factors and zero activation energies while isolating `B-SYN`; if methanol appears, the issue is kinetic scale/units. If methanol stays absent, inspect the Aspen POWERLAW/RPLUG specification.

Methanol production tuning campaign:

```python
from aspen_automation import run_methanol_tuning_campaign

campaign = run_methanol_tuning_campaign(
    "process_library/methanol",
    "process_runs/batch_first_capsule",
    visible=True,
    max_cases=40,
    promote=True,
)
```

Use this after a readable Gate 2 run. It creates temporary variant specs, runs staged batch-first Aspen cases, writes `tuning_campaign_summary.csv`, `tuning_campaign_summary.json`, and `best_process.yaml`, and promotes the winner only when the stop rule is met.

## Result Artifacts

Each successful run should write:

- `methanol_generated.inp` or equivalent generated INP.
- Batch `.his`, `.bkp`, stdout, and stderr.
- `results/context_probe.json`.
- `results/build_diagnostics.json`.
- `results/simulation_diagnostics.json`.
- `results/acceptance.json`.
- `results/kpis.json`.
- `results/streams.csv`.
- `results/blocks.csv`.
- `results/material_balance.csv`.
- `results/energy_balance.csv`.
- `live_aspen_summary.json` in the run directory.
- Optional HTML/Markdown report directory.
- For tuning campaigns: `tuning_campaign_summary.csv`, `tuning_campaign_summary.json`, variant `process.yaml` files, and `best_process.yaml`.

When escalating to IT, include `live_aspen_summary.json`, generated `.his`, `context_probe.json`, stdout/stderr, Event Viewer excerpts if available, OS/.NET version, exact missing assembly messages, and Fusion/.NET logs if available. Ask for AppsAnywhere "Pre-fetch all" and package repair for missing Aspen localization assemblies.

## Test Contract

Before claiming a port or major change works, run focused unit tests and the non-integration suite:

```powershell
pixi run pytest tests/test_inp_generator.py tests/test_validator.py tests/test_process_library.py -q --basetemp=.codex_pytest_tmp_aspen_focused
pixi run pytest tests/test_notebook_purpose_contract.py tests/test_batch_engine.py tests/test_capsule_context.py -q --basetemp=.codex_pytest_tmp_aspen_contract
pixi run pytest tests -q --ignore=tests/integration --basetemp=.codex_pytest_tmp_aspen_all
```

Live tests should be split:

1. Batch translator acceptance: generated INP emits clean `.bkp`.
2. Capsule/BKP load: `.bkp` loads through COM and readable CSV/JSON results are produced.
3. Process credibility: product stream and chemistry make physical sense.
4. Nameplate acceptance: enforce production/purity/energy targets only after earlier gates are stable.

## Debug Paths

Useful Aspen tree paths:

- Stream input temperature: `\Data\Streams\STREAM\Input\TEMP\MIXED`
- Stream output temperature: `\Data\Streams\STREAM\Output\TEMP_OUT\MIXED`
- Stream output pressure: `\Data\Streams\STREAM\Output\PRES_OUT\MIXED`
- Block duty: `\Data\Blocks\BLOCK\Output\QNET`

When streams or blocks are missing after load, treat it as an INP translation/BKP load problem before editing result extraction.
