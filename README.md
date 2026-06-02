# Aspen Plus Batch-First Automation

This repository builds, runs, diagnoses, and tunes Aspen Plus process simulations from schema-first `process.yaml` specifications.

The supported workflow is:

```text
process.yaml -> generate_inp -> Aspen batch .his/.bkp gate -> InitFromArchive2 -> CSV/JSON extraction -> notebook diagnostics
```

The main user surface is the process-agnostic `notebooks/process_library_runner.ipynb`.
The methanol case is a separate worked example at `notebooks/methanol_example_runner.ipynb`.

## Quick Start

1. Launch Aspen Plus from AppsAnywhere/Porticada or your local Aspen installation.
2. Confirm the supported Pixi environment manager is available, then create the project environment:

```powershell
pixi --version
pixi install
pixi run install-kernel
```

3. Open the generic process notebook:

```powershell
pixi run process-library-notebook
```

4. Restart the notebook kernel and run cells top-to-bottom.

For a new process, fill the process-intake cell to write `source_manifest.json`, `process_research_brief.md`, and `codex_process_yaml_prompt.md`; then use Codex to create or revise `process_library/<process_name>/process.yaml`.

For the worked methanol example and tuning campaign:

```powershell
pixi run methanol-example-notebook
```

The canonical 10k TPD methanol screening case lives at `process_library/methanol/process.yaml`, but it is an example/regression fixture rather than the default assumption for every process.

## Repository Layout

```text
aspen_automation/       Supported Python package
process_library/        Canonical process specs
notebooks/              Generic live workflow plus methanol example notebook
tests/                  Unit, contract, integration, and fixtures
docs/                   Maintained user, developer, and reference documentation
templates/              Legacy-compatible YAML/INP templates
legacy_old_files/       Preserved unsupported probes, artifacts, and historical docs
.codex/                 Codex skills and portable Aspen workflow bundle
```

## Validation

Run the supported non-integration suite:

```powershell
pixi run test
```

For a focused validation/orchestration check:

```powershell
pixi run test-focused
```

Direct `python -m pytest ...` runs are useful only as emergency diagnostics when Pixi is unavailable; the supported project path is the Python 3.12 Pixi workspace in `pixi.toml`.

Live Aspen validation is split into:

1. Gate 1 batch translation: generated INP emits clean `.his` and `.bkp`.
2. Gate 2 BKP COM load/extraction: readable CSV/JSON results.
3. Process acceptance: production and purity targets enforced only after readable results are stable.

## Current Methanol Target

The canonical methanol spec is tuned to the live-validated screening target:

- Component CH3OH production: about `10000 TPD`
- Total `MEOH-PRO`: about `10001 TPD`
- CH3OH purity: about `99.99 wt%`
- Product stream: `MEOH-PRO`

Historical COM experiments, old generated Aspen files, manual probes, and old planning notes were preserved under `legacy_old_files/` for reference.
