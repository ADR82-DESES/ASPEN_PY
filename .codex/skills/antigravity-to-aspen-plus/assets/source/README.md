# Bundled Aspen Automation Source

This directory is a portable snapshot of the schema-first, batch-first Aspen Plus workflow used by the `antigravity-to-aspen-plus` skill.

## What To Copy

Use the skill bootstrap script from the skill root:

```powershell
python .codex\skills\antigravity-to-aspen-plus\scripts\bootstrap_aspen_automation.py --target .
```

The script copies the automation package, notebook, process-library example, tests, and environment files into a clean project without overwriting different existing files unless `--force` is supplied.

## Included Workflow

The normal live workflow is:

```text
process.yaml -> generate_inp -> Aspen batch .his/.bkp gate -> InitFromArchive2 -> CSV/JSON extraction -> notebook diagnostics
```

The notebook-first surface is `notebooks/process_library_runner.ipynb`. A user should launch Aspen Plus from AppsAnywhere/Porticada or a local Aspen install, open the notebook, restart the kernel, and run cells top-to-bottom.

## Methanol Example

`process_library/methanol/process.yaml` is the working ATR-like methanol screening case. The validated 10k TPD configuration uses:

- `NG-FEED=440000 kg/hr`
- `STEAM=297000 kg/hr`
- `O2-FEED=528000 kg/hr`
- `B-SYN RPLUG LENGTH=19.613`
- `B-SYN DIAM=4.0`
- `PURGE=0.15`, `RECYCLE=0.85`
- `process_defaults.product_stream=MEOH-PRO`

The live validated case produced about `10000.06 TPD` component CH3OH and `99.9878 wt%` CH3OH in `MEOH-PRO`.

## Validation

For a port or source update, run:

```powershell
pixi run pytest tests/test_process_library.py tests/test_methanol_tuning.py tests/test_inp_generator.py tests/test_validator.py tests/test_notebook_purpose_contract.py -q --basetemp=.codex_pytest_tmp_aspen_focused
pixi run pytest tests -q --ignore=tests/integration --basetemp=.codex_pytest_tmp_aspen_all
```

Live validation should be split into Gate 1 batch translation, Gate 2 BKP COM load/extraction, and final acceptance with targets enforced only after readable results are stable.
