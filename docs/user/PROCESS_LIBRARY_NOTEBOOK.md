# Process Library Notebook Workflow

This repository has two notebook surfaces:

- `notebooks/process_library_runner.ipynb`: process-agnostic intake, YAML validation, Gate 1 batch translation, Gate 2 BKP COM load/extraction, diagnostics, and CSV analysis.
- `notebooks/methanol_example_runner.ipynb`: methanol-only example, kinetic diagnostics, remediation, tuning campaign, and 10k TPD screening lessons.

## Folder Structure

```text
process_library/
  <process_name>/
    process.yaml
    assets/
      source_manifest.json
      process_research_brief.md
      codex_process_yaml_prompt.md

process_runs/
  batch_first_capsule/
    <process_name>/
      run_<timestamp>/
        results/
        reports/
        session/

notebooks/
  process_library_runner.ipynb
  methanol_example_runner.ipynb
```

- `process_library/` is the source of truth for process definitions.
- Each direct subfolder under `process_library/` is one process.
- Each process folder should contain a canonical `process.yaml`.
- `process_runs/` is generated output and is ignored by git.

## Generic Process Workflow

Use `process_library_runner.ipynb` for any user-defined chemical process:

0. In PowerShell, confirm Pixi is available and install the workspace:

```powershell
pixi --version
pixi install
```

1. Fill `PROCESS_NAME`, `USER_PROCESS_BRIEF`, `SOURCE_PDFS`, `SOURCE_URLS`, `WEB_SEARCH_QUERIES`, and `REFERENCE_NOTES`.
2. Set `WRITE_PROCESS_INTAKE_ARTIFACTS=True` to write the Codex handoff files under `process_library/<process_name>/assets/`.
3. Ask Codex to use `codex_process_yaml_prompt.md` plus the source artifacts to create or revise `process_library/<process_name>/process.yaml`.
4. Re-run the notebook to discover the process, validate YAML, run coherence review, and execute Gate 1/Gate 2 when Aspen is available.

The notebook records web-search queries and source URLs, but does not perform hidden web browsing or call an LLM from the kernel.

## YAML Format

`process.yaml` uses the existing plant specification schema. Required top-level sections:

- `metadata`
- `components`
- `properties`
- `flowsheet`
- `streams`
- `blocks`

Optional supported sections:

- `flowsheeting_options`
- `chemistry`
- `reaction_sets`
- `kinetic_models`
- `process_defaults`
- `targets`

The methanol file at `process_library/methanol/process.yaml` is the reference example and regression fixture. Do not copy methanol-specific equipment, reactions, or KPI assumptions into unrelated processes by default.

## Batch-First Gates

The generic notebook:

1. Runs Aspen pre-flight checks.
2. Discovers process folders.
3. Validates each `process.yaml`.
4. Runs schema/coherence review.
5. Generates INP and runs Gate 1 batch translation.
6. Treats `.his` status as the source of truth; `.bkp` existence alone is not success.
7. Runs Gate 2 BKP COM load/extraction with `run_process_batch_first`.
8. Writes `context_probe.json`, diagnostics, result CSVs, reports, and `live_aspen_summary.json`.
9. Builds process-agnostic Codex analysis from result CSV artifacts.

## Methanol Example

Use `methanol_example_runner.ipynb` only for the bundled methanol case. It keeps the kinetic remediation, synthesis-loop diagnostics, purge/ATR tuning worksheet, and live tuning campaign separate from the generic user workflow.

Open it with:

```powershell
pixi run methanol-example-notebook
```

Run the normal non-integration test suite with:

```powershell
pixi run test
```
