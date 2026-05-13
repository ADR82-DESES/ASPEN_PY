# Bundled Aspen Automation Source

This directory is a portable source snapshot for the batch-first Aspen Plus workflow.

Included:

- `aspen_automation/`: schema, INP generation, Aspen batch runner, COM session/load helpers, extraction, diagnostics, context probing, methanol tuning, and analysis helpers.
- `notebooks/process_library_runner.ipynb`: notebook-only Gate 1/Gate 2 live workflow, with outputs cleared for portability.
- `process_library/methanol/process.yaml`: working methanol process-library example tuned to the validated 10k TPD screening case.
- `tests/`: unit, contract, and integration tests from the source project.
- `pyproject.toml` and `pixi.toml`: dependency/test environment references.

Use `../scripts/bootstrap_aspen_automation.py` from the skill root to copy this source into a clean project. Existing files are skipped by default unless `--force` is supplied.

The bundled methanol example uses the live-validated target configuration: `NG-FEED=440000 kg/hr`, `STEAM=297000 kg/hr`, `O2-FEED=528000 kg/hr`, `B-SYN RPLUG LENGTH=19.613`, `DIAM=4.0`, and `MEOH-PRO` as the product stream.
