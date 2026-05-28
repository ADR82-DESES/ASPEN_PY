# Report Generation

This document describes `generate_reports(results, spec, output_dir, format)` from `aspen_automation.reporter`.

## Function

```python
generate_reports(results, spec, output_dir="results/", format="html") -> str
```

- Writes CSV + JSON artifacts and a summary file.
- Prints a console summary.
- Returns the run directory path.

## Output Directory Structure

Each run is written to:

```text
run_YYYY-MM-DD_HH-MM-SS/
```

Generated files:

- `streams.csv`
- `blocks.csv`
- `material_balance.csv`
- `energy_balance.csv`
- `kpis.json`
- `diagnostics.json`
- `run_summary.html` (or `run_summary.md` when `format="markdown"`)

## CSV Format

`streams.csv`
- Contains extracted stream properties and component fraction columns (including `stream_name`, flow, temperature, pressure).

`blocks.csv`
- Contains per-block performance fields (`block_name`, `block_type`, `duty`, `conversion`, `efficiency`).

`material_balance.csv`
- Contains component material balance terms (`component`, input/output rates, closure `%`).

`energy_balance.csv`
- Contains per-block duty rows and aggregate totals (typically including `TOTAL`).

## JSON Format

`kpis.json`
- Key-value map of KPI results:
  `production_rate_tpd`, `purity_fraction`, `energy_consumption_mw`, `yield_fraction`, `convergence_status`.

`diagnostics.json`
- Key-value map of run diagnostics and status details (for example, error counts, warning counts, convergence metadata).
- Batch-first process-library runs also write `build_diagnostics.json` and
  `simulation_diagnostics.json`; these include `model_quality_warnings` and
  `nrtl_binary_parameters_status` when NRTL binary-parameter coverage is relevant.

## HTML Format

- Summary is written to `run_summary.html`.
- Uses inline CSS styles.
- Convergence status is color-coded:
  - Green (`#27ae60`) when status is `"converged"`.
  - Red (`#e74c3c`) for other statuses.
- Includes KPI table and top-10 preview tables for streams and blocks.

## Markdown Format

- Summary is written to `run_summary.md`.
- Uses `##` section headers.
- Uses pipe tables (`| ... |`) for KPI, streams, and blocks sections.
- Streams and blocks sections include top-10 rows.

## Console Summary Format

- Starts with a separator line of `"=" * 80`.
- Prints convergence status.
- Prints KPI values.
- Prints generated filenames from the run directory.

## Usage Example

```python
from aspen_automation import generate_reports

run_dir = generate_reports(results, spec, output_dir="results/", format="html")
```
