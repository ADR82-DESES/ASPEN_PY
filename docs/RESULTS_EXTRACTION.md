# Results Extraction

This document describes `extract_results(aspen, spec)` from `aspen_automation.extractor`.

## Function

```python
extract_results(aspen, spec) -> dict
```

- `aspen`: Aspen Plus COM document instance.
- `spec`: `PlantSpecification` or equivalent dict.
- Returns a dictionary with DataFrames (`streams`, `blocks`, `material_balance`, `energy_balance`) plus `kpis`, `diagnostics`, and `metadata`.

## COM Tree Paths

| Property | Path pattern |
| :--- | :--- |
| `TEMP_OUT` | `\Data\Streams\{stream}\Output\TEMP_OUT\MIXED` |
| `PRES_OUT` | `\Data\Streams\{stream}\Output\PRES_OUT\MIXED` |
| `MASSFLMX` | `\Data\Streams\{stream}\Output\MASSFLMX\MIXED` |
| `MOLEFLMX` | `\Data\Streams\{stream}\Output\MOLEFLMX\MIXED` |
| `MOLEFRAC` | `\Data\Streams\{stream}\Output\MOLEFRAC\MIXED\{component}` |
| `MASSFRAC` | `\Data\Streams\{stream}\Output\MASSFRAC\MIXED\{component}` |

## Streams DataFrame Schema

Base columns:

| Column | Type | Units / meaning |
| :--- | :--- | :--- |
| `stream_name` | `str` | Aspen stream identifier |
| `temperature` | `float \| None` | stream temperature |
| `pressure` | `float \| None` | stream pressure |
| `mass_flow` | `float \| None` | mixed-stream mass flow |
| `mole_flow` | `float \| None` | mixed-stream mole flow |

Dynamic component columns (for each component id in spec):

| Column pattern | Type | Meaning |
| :--- | :--- | :--- |
| `{component}_mole_frac` | `float \| None` | mole fraction in stream |
| `{component}_mass_frac` | `float \| None` | mass fraction in stream |

## Blocks DataFrame Schema

| Column | Type | Meaning |
| :--- | :--- | :--- |
| `block_name` | `str` | Aspen block identifier |
| `block_type` | `str \| None` | Aspen block type |
| `duty` | `float \| None` | block duty (`QNET`/`DUTY`) |
| `conversion` | `float \| None` | conversion value |
| `efficiency` | `float \| None` | efficiency value |

## KPI Dictionary

`kpis` contains:

| Key | Type | Units / meaning |
| :--- | :--- | :--- |
| `production_rate_tpd` | `float \| None` | tons/day |
| `purity_fraction` | `float \| None` | fraction (0-1) |
| `energy_consumption_mw` | `float \| None` | MW |
| `yield_fraction` | `float \| None` | fraction (0-1) |
| `convergence_status` | `str \| None` | simulation status |

## Purity Expression Syntax

Grammar:

```text
<expression> := <component> <basis> "in" <stream>
<basis> := "wt%" | "mol%" | "mass fraction" | "mole fraction"
```

Examples:

- `CH3OH wt% in MEOH-PRO`
- `H2O mol% in WATER-OUT`

## Usage Example

```python
from aspen_automation import extract_results

results = extract_results(aspen, spec)
```
