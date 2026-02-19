# Plant Specification Schema Reference

This document describes the YAML/JSON schema used for automating Aspen Plus plant simulations. The schema is designed to mirror the structure of Aspen Plus INP files while providing modern validation and type safety.

## 1. Schema Overview

The specification is a hierarchical structure containing metadata, component definitions, property methods, flowsheet connectivity, stream definitions, and block parameters.

## 2. Metadata Section

Defines the simulation title and units of measure.

| Field | Type | Description |
| :--- | :--- | :--- |
| `title` | string | Title of the simulation |
| `description` | string (optional) | Detailed description of the plant |
| `units` | object | Unit system definition |

### Units Object

| Field | Type | Allowed Values |
| :--- | :--- | :--- |
| `pressure` | string | `bar`, `psi`, `atm`, `kPa`, `MPa` |
| `temperature` | string | `C`, `F`, `K`, `R` |
| `flow` | string | `kg/hr`, `kmol/hr`, `lb/hr`, `lbmol/hr` |

## 3. Components Section

List of chemical components used in the simulation.

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | string | Aspen ID (e.g., "CH4") |
| `name` | string | Full name (e.g., "METHANE") |
| `formula` | string (optional) | Chemical formula |

## 4. Properties Section

Defines thermodynamic methods and databases.

| Field | Type | Description |
| :--- | :--- | :--- |
| `method` | string | Property method (e.g., "RK-SOAVE", "PENT-ROB") |
| `databanks` | list[string] (optional) | Aspen databanks to use |

## 5. Flowsheet Section

Defines how streams connect to blocks.

| Field | Type | Description |
| :--- | :--- | :--- |
| `block` | string | Name of the block (must exist in blocks section) |
| `inputs` | list[string] | List of input stream names |
| `outputs` | list[string] | List of output stream names |

## 6. Streams Section

Defines stream conditions and composition.

| Field | Type | Description |
| :--- | :--- | :--- |
| `name` | string | Unique stream name |
| `temperature` | number | Stream temperature |
| `pressure` | number | Stream pressure |
| `mass_flow` | number (optional*) | Total mass flow (required if mole_flow missing) |
| `mole_flow` | number (optional*) | Total mole flow (required if mass_flow missing) |
| `composition` | object | Map of component ID to fraction (sum must be 1.0) |

## 7. Blocks Section

Defines unit operations.

| Field | Type | Description |
| :--- | :--- | :--- |
| `name` | string | Unique block name |
| `type` | string | Aspen block type (e.g., "MIXER", "RGIBBS", "FLASH2") |
| `parameters` | object (optional) | Key-value pairs of block settings |

## 8. Chemistry Section (Optional)

Defines chemical reaction sets and stoichiometry.

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | string | Unique chemistry ID |
| `reactions` | list[object] | List of reaction definitions |

### Reaction Object

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | integer | Reaction sequence number |
| `stoichiometry` | list[object] | List of component stoichiometry |

### Stoichiometry Object

| Field | Type | Description |
| :--- | :--- | :--- |
| `component` | string | Component ID |
| `coefficient` | number | Stoichiometric coefficient (negative for reactants) |

## 9. Targets Section (Optional)

Defines production targets and purity requirements for optimization.

| Field | Type | Description |
| :--- | :--- | :--- |
| `production_rate_tpd` | number | Target production rate in metric tons per day |
| `tolerance` | number | Convergence tolerance (default: 0.01) |
| `purity` | object (optional) | Purity constraints |

### Purity Object

| Field | Type | Description |
| :--- | :--- | :--- |
| `expression` | string | Fortran-style expression for purity |
| `min_value` | number | Minimum target purity fraction |

## 10. Validation Rules

The `aspen_automation` package enforces 8 core validation rules (see [VALIDATION_RULES.md](VALIDATION_RULES.md) for details and examples):

1.  **Schema Structure**: All required sections (metadata, components, etc.) must be present.
2.  **Component References**: Every component in a stream's composition must be defined in the components section.
3.  **Stream Connectivity**: Every stream in the flowsheet must be defined in the streams section.
4.  **Composition Validation**: All composition sums must equal 1.0 ± 0.001.
5.  **Block References**: Every block in the flowsheet must be defined in the blocks section.
6.  **Unit Validation**: Only allowed Aspen Plus units are permitted.
7.  **Required Fields**: Critical fields (e.g., temperature, pressure) must be provided.
8.  **Type Validation**: Values must match their expected data types (e.g., numeric for flows).

## 11. API Usage Example

```python
from aspen_automation import load_spec, ValidationError

try:
    spec = load_spec("my_plant.yaml")
    print(f"Loaded: {spec.metadata.title}")
except ValidationError as e:
    print(e)
```
