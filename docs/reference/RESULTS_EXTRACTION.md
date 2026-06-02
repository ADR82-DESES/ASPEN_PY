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
- RPLUG duty fallbacks after `QNET`/`DUTY`: `QCALC`, `QREAC`, `QREACT`, `QRXN`
- `\Data\Blocks\{block}\Output\WNET`
- `\Data\Blocks\{block}\Output\CONV`
- `\Data\Blocks\{block}\Output\EFF`

Aspen exposes heat/work rates for this batch-first workflow in `CAL/SEC`.
The extractor preserves those raw values and converts reported SI columns using:

```text
1 CAL/SEC = 0.004184 kW = 0.000004184 MW
```

### Convergence diagnostics

- `\Data\Results Summary\Run-Status\Output\PER_ERROR`
- `\Data\Results Summary\Run-Status\Output\NERROR`
- `\Data\Results Summary\Run-Status\Output\NWARN`

Missing COM nodes are handled safely and converted to `None`/`NaN` (no crash).

## DataFrame Schemas

### `streams`

Base columns:

- `stream_name`
- `extraction_status` (`direct`, `missing`, or `inferred_by_block_closure`)
- `extraction_source`
- `extraction_note`
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
- `duty` (alias of corrected `duty_kw`)
- `duty_kw` (converted from Aspen `CAL/SEC`)
- `duty_mw` (converted from Aspen `CAL/SEC`)
- `duty_raw`
- `duty_raw_unit`
- `duty_source`
- `condenser_duty_raw`, `condenser_duty_kw`, `condenser_duty_mw`, `condenser_duty_source`
- `reboiler_duty_raw`, `reboiler_duty_kw`, `reboiler_duty_mw`, `reboiler_duty_source`

Aspen heat-duty output values are stored with raw provenance. For this workflow
the raw Aspen duty basis is `CAL/SEC`; corrected `kW` and `MW` fields use
`1 CAL/SEC = 0.004184 kW`. For RADFRAC, condenser and reboiler duties are also
reported separately. When condenser/reboiler duties are available for a RADFRAC
block, the aggregate `duty_mw` is the captured absolute condenser plus reboiler
duty, overriding Aspen's occasional direct `DUTY=1` placeholder so energy
consumption remains a captured-duty metric rather than a silent net cancellation.
- `net_work_kw`
- `net_work_mw`
- `net_work_raw`
- `net_work_raw_unit`
- `net_work_source`
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
- `duty` (alias of corrected `duty_kw`)
- `duty_kw`
- `duty_mw`
- `duty_raw`
- `duty_raw_unit`
- `duty_source`

Optional summary (`energy_balance_view="summary"`):

- `category` in `["Heat Input", "Heat Output", "Net Work"]`
- `value_mw`

## KPI Definitions

`kpis` contains:

- `production_rate_tpd`: selected product stream `mass_flow * 24 / 1000`
- `purity_fraction`: value from purity expression evaluation
- `energy_consumption_mw`: `sum(abs(duty_mw))` after converting Aspen `CAL/SEC` duties to MW
- `energy_unit_basis`: raw unit and conversion metadata
- `yield_fraction`: `product_mole_flow / max(feed_mole_flow)`
- `convergence_status`: `"converged" | "failed" | "unknown"`

Acceptance gates may also validate `targets.product_conditions`, such as
`MEOH-PRO` pressure `1.5 bar +/- 0.05 bar`, from the extracted `streams.csv`
pressure and temperature fields.

Component-loss gates from `targets.component_loss_limits` evaluate an extracted
stream/component mass flow using either direct component mass-flow fields or
`mass_flow * {component}_mass_frac`. `acceptance.json` and
`simulation_diagnostics.json` include `component_loss_checks`. When the gate is
used for methanol LIGHTS recovery, `lights_recovery` reports:

- `vent_stream`
- `vent_methanol_loss_kg_hr`
- `vent_methanol_loss_tpd`
- `baseline_lights_methanol_loss_kg_hr`
- `lights_methanol_recovered_kg_hr`
- `lights_methanol_recovery_fraction`

Product stream selection priority:

1. `process_defaults.product_stream`, when declared
2. product-stream topology from the flowsheet
3. highest `mass_flow` among the candidate product streams

## Model-Quality Diagnostics

Batch-first runs promote Aspen physical-property warnings from the `.his` file into
`build_diagnostics.json` and `simulation_diagnostics.json` as
`model_quality_warnings`. NRTL methanol/water coverage is also summarized with:

- `nrtl_binary_parameters_status`: `missing`, `provided`, `accepted_by_aspen`, `warning_from_aspen`, or a non-applicable status
- `nrtl_binary_parameters`: required pairs, provided pairs, missing pairs, source/provenance metadata, and whether Aspen reported the zero-parameter fallback warning
- `batch_history_diagnostics`: parsed batch `.his` status and messages
- `post_com_history_diagnostics`: parsed COM-saved `.his` status when an output archive history exists
- `combined_model_quality_warnings`: de-duplicated model-quality warnings across available histories

For the canonical methanol model, a clean Gate 1 history should report
`nrtl_binary_parameters_status="accepted_by_aspen"`. The final purification
coherence warning should be absent when `B-DIST` is a complete RADFRAC column.

## Stream Inference

Direct Aspen COM extraction remains the source of truth. Aspen stream IDs are also
retried using the 8-character Aspen alias when a YAML stream name is longer than
Aspen's displayed identifier; for example, `WASTE-H2O` may be extracted from
`WASTE-H2` while retaining the YAML name in `streams.csv`. If a nonreactive
separator block (`SEP`, `FLASH2`, or `FSPLIT`) has exactly one input, exactly two
outputs, and one output stream is blank, the extractor infers the blank output by
component-wise mass closure after direct extraction. Inferred rows are marked with
`extraction_status="inferred_by_block_closure"` and keep mole-flow fields blank
unless Aspen directly provided them.

Extraction diagnostics include:

- `stream_extraction`: inferred streams, blank streams before/after inference, and warnings
- `stream_extraction.blank_radfrac_product_streams`: RADFRAC terminal products that remained blank; these are not inferred by closure
- `terminal_mass_closure`: topology-level feed/product mass closure using the extracted and inferred stream rows

`RADFRAC` terminal products must be extracted directly from Aspen. Separator
mass-closure inference remains available for coarse `SEP`, `FLASH2`, and
`FSPLIT` blocks only.

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
