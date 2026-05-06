# Process Library Notebook Workflow

This repository now supports a notebook-driven process library built on top of the existing Aspen automation pipeline.

## Folder Structure

```text
process_library/
  methanol/
    process.yaml
    assets/

process_runs/
  <process_name>/
    run_<timestamp>/
      <process_name>_generated.inp
      <process_name>_output.apw
      results/
      reports/
      session/

notebooks/
  process_library_runner.ipynb
```

- `process_library/` is the source-of-truth library for process definitions.
- Each direct subfolder under `process_library/` is one process.
- Each process folder should contain a canonical `process.yaml`.
- `process_runs/` is generated output and is ignored by git.

## How To Add A New Chemical Process

1. Create a new folder under `process_library/`, for example `process_library/ammonia/`.
2. Add `process.yaml` in that folder.
3. Optionally add supporting files under `assets/` if the process needs local references.
4. Run `notebooks/process_library_runner.ipynb`.

The notebook discovers process folders automatically, validates the YAML, runs a pre-run coherence review, and only executes processes whose specifications pass that gate.

## YAML Format

`process.yaml` should use the same plant specification schema already used by the existing methanol template. The required top-level sections are:

- `metadata`
- `components`
- `properties`
- `flowsheet`
- `streams`
- `blocks`

Optional sections already supported by the current generator can also be used:

- `flowsheeting_options`
- `chemistry`
- `reaction_sets`
- `targets`

The sample file `process_library/methanol/process.yaml` is the reference starting point for new processes.

## How The Notebook Runs

The notebook:

1. Resolves the repository root.
2. Points to `process_library/` as the process source.
3. Scans all direct process folders.
4. Validates each YAML file using the existing spec validator.
5. Runs a per-process Codex-style coherence review against the YAML to catch semantic issues before execution.
6. When coherence fails, proposes concrete YAML improvements, asks whether they should be applied to the original `process.yaml`, writes a timestamped backup, and reruns validation/coherence.
7. Reuses the current Aspen workflow only for processes that pass coherence:
   - generate an INP file,
   - run the session,
   - save an APW output,
   - extract results,
   - write CSV/JSON summaries,
   - generate reports.
8. Writes each process run into `process_runs/<process_name>/run_<timestamp>/`.
9. Adds a per-process post-run Codex analysis section that reads `streams.csv`, `blocks.csv`, `material_balance.csv`, and `energy_balance.csv` directly from the generated run artifacts.

Errors in one process are reported in the notebook summary and do not stop later processes from being discovered or attempted.

## Pixi Environment

This repo now includes [pixi.toml](../pixi.toml) so the notebook can run in a reproducible Windows environment that matches the Aspen workflow dependencies.

Create the environment:

```bash
pixi install
```

Launch JupyterLab:

```bash
pixi run lab
```

Open the process library notebook directly:

```bash
pixi run process-library-notebook
```

If you want the kernel to appear explicitly in Jupyter, install it once:

```bash
pixi run install-kernel
```

If you open the notebook in VS Code instead of JupyterLab:

1. Use `Python: Select Interpreter`.
2. Choose `.\.pixi\envs\default\python.exe`.
3. Open the notebook kernel picker and select `Python (aspen-py-pixi)`.

The repository includes a workspace setting that points VS Code at the Pixi interpreter by default. If it still does not appear, reload the VS Code window after selecting the interpreter.

## Current Limitation

The process YAML stays intentionally close to the existing methanol template schema. Runtime metadata such as output paths and generated filenames are derived from the process folder name and notebook configuration rather than being authored inside YAML.
