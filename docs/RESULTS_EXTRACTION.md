# Results Extraction

`aspen_automation.extractor.extract_results(aspen, spec, energy_balance_view="legacy")` extracts Aspen Plus COM tree data and returns a structured result object with pandas DataFrames.

## Return Shape

```python
{
    "streams": pd.DataFrame,
    "blocks": pd.DataFrame,
    "material_balance": pd.DataFrame,
    "energy_balance": pd.DataFrame,
    "kpis": dict,
    "diagnostics": dict,
    "metadata": dict,
}
```

## COM Paths Used

### Stream properties

- `\Data\Streams\{stream}\Output\TEMP_OUT\MIXED`
- `\Data\Streams\{stream}\Output\PRES_OUT\MIXED`
- `\Data\Streams\{stream}\Output\MASSFLMX\MIXED`
- `\Data\Streams\{stream}\Output\MOLEFLMX\MIXED`
- `\Data\Streams\{stream}\Output\MOLEFRAC\MIXED\{component}`
- `\Data\Streams\{stream}\Output\MASSFRAC\MIXED\{component}`

### Block performance

- `\Data\Blocks\{block}\Input\TYPE`
- `\Data\Blocks\{block}\Output\QNET` (fallback: `DUTY`)
- `\Data\Blocks\{block}\Output\WNET`
- `\Data\Blocks\{block}\Output\CONV`
- `\Data\Blocks\{block}\Output\EFF`

### Convergence diagnostics

- `\Data\Results Summary\Run-Status\Output\PER_ERROR`
- `\Data\Results Summary\Run-Status\Output\NERROR`
- `\Data\Results Summary\Run-Status\Output\NWARN`

Missing COM nodes are handled safely and converted to `None`/`NaN` (no crash).

## DataFrame Schemas

### `streams`

Base columns:

- `stream_name`
- `temperature`
- `pressure`
- `mass_flow`
- `mole_flow`

Per component (from `spec.components[*].id`):

- `{component}_mole_frac`
- `{component}_mass_frac`

### `blocks`

- `block_name`
- `block_type`
- `duty` (alias of `duty_kw`)
- `duty_kw`
- `duty_mw`
- `net_work_kw`
- `conversion`
- `efficiency`

### `material_balance`

- `component_id`
- `component` (compatibility alias)
- `input_kmol_hr`
- `output_kmol_hr`
- `closure_pct`
- `closure_%` (compatibility alias)

Feed streams and product streams are inferred from flowsheet topology:

- feeds: streams used as inputs but never produced as outputs
- products: streams produced as outputs but never reused as inputs

### `energy_balance`

Default (`energy_balance_view="legacy"`):

- `block_name` (includes per-block rows plus `TOTAL`)
- `duty` (alias of `duty_kw`)
- `duty_kw`
- `duty_mw`

Optional summary (`energy_balance_view="summary"`):

- `category` in `["Heat Input", "Heat Output", "Net Work"]`
- `value_mw`

## KPI Definitions

`kpis` contains:

- `production_rate_tpd`: selected product stream `mass_flow * 24 / 1000`
- `purity_fraction`: value from purity expression evaluation
- `energy_consumption_mw`: `sum(abs(duty_kw)) / 1000`
- `yield_fraction`: `product_mole_flow / max(feed_mole_flow)`
- `convergence_status`: `"converged" | "failed" | "unknown"`

Product stream selection priority:

1. stream named `MEOH-PRO`
2. stream with max `CH3OH_mass_frac`
3. stream with max `mass_flow`

## Purity Expression Syntax

Format:

```text
<component> <basis> in <stream>
```

Supported basis tokens:

- `wt%`, `mass%`, `weight%`, `mass fraction`
- `mol%`, `mole%`, `mole fraction`

Examples:

- `CH3OH wt% in MEOH-PRO`
- `CH3OH mol% in MEOH-PRO`

If `spec.targets.purity` is absent, `purity_fraction` is `None`.

## Usage

```python
from aspen_automation import extract_results

results = extract_results(aspen, spec)
print(results["streams"].head())
print(results["kpis"])

# Optional: aggregated category view for energy balance
summary_results = extract_results(aspen, spec, energy_balance_view="summary")
print(summary_results["energy_balance"])
```
