---
name: antigravity-to-aspen-plus
description: Build and run Aspen Plus simulations in this repo from an Antigravity process specification. Use when Codex needs to turn a process description into the repo schema, verify Aspen Plus COM access, define components and thermodynamics, create streams, blocks, and flowsheet connections, run the case, and export results.
---

# Antigravity to Aspen Plus

Use the repo's schema-first path. Prefer reusing the existing automation code over writing raw Aspen COM logic from scratch.

## Precedence

If both this skill and `.agent/rules/aspen-plus.md` apply, follow this skill for workflow, file selection, and implementation patterns because it is repo-specific and task-specific. Use `.agent/rules/aspen-plus.md` only as background guidance for general Aspen COM behavior when this skill is silent.

## Workflow

1. Translate the Antigravity output into the repo spec shape used by `templates/*.yaml`: `metadata`, `components`, `properties.method`, `flowsheet`, `streams`, and `blocks`.
2. Put thermodynamics in `properties.method`, streams in `streams`, unit ops in `blocks`, and wiring in `flowsheet`.
3. Validate before opening Aspen. Reuse `load_spec(...)` and `validate_spec(...)`; fix undefined streams or blocks, duplicate names, and compositions that do not sum to 1.0.
4. Build through `generate_inp(...)` plus `run_simulation_session(..., build_mode="auto")`. This is the stable path for opening Aspen, checking COM, importing the generated case, and running it.
5. Save and export with `extract_results(...)` or the patterns in `run_methanol_plant.py`.

## Reuse These Files

- `run_methanol_plant.py`: end-to-end example from spec to Aspen run to CSV/JSON export.
- `aspen_automation/session.py`: COM connection, `InitNew`, import/load fallback, `Reinit`, `Engine.Run2`, and convergence checks.
- `aspen_automation/extractor.py`: stream, block, KPI, and report extraction.
- `templates/methanol_plant_atr.yaml`: reference layout for components, thermo, streams, blocks, and connections.

## Aspen COM Rules

- Initialize Aspen before touching `aspen.Tree`. Use `InitNew()`, import a generated `.inp`, or load an archive.
- Set `SuppressDialogs = 1`; keep `Visible = True` while debugging.
- Use absolute file paths for Aspen COM file operations.
- Write to `\Data\...\Input\...` nodes and read from `\Data\...\Output\...` nodes.
- If streams or blocks are missing after import, treat that as a build/load problem first.

## Minimal Pattern

```python
from aspen_automation import extract_results, generate_inp, load_spec, run_simulation_session

spec = load_spec("templates/my_case.yaml")
generate_inp(spec, output_path="temp/my_case.inp")
session = run_simulation_session(
    spec,
    build_mode="auto",
    output_dir="temp/session",
    keep_alive=True,
    visible=True,
)

if str(session.convergence_status).lower() != "converged":
    raise RuntimeError(session.convergence_status)

results = extract_results(session.aspen, spec)
```

## Debug Paths

- Stream input temperature: `\Data\Streams\STREAM\Input\TEMP\MIXED`
- Stream output temperature: `\Data\Streams\STREAM\Output\TEMP_OUT\MIXED`
- Stream output pressure: `\Data\Streams\STREAM\Output\PRES_OUT\MIXED`
- Block duty: `\Data\Blocks\BLOCK\Output\QNET`
