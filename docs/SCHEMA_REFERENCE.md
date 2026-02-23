# Aspen Automation Schema Reference

This document describes the schema for the Aspen Plus automation package. The schema is designed to closely mirror the structure of Aspen Plus `.inp` files, facilitating the generation of simulation input files.

## Overview

The specification is provided as a YAML or JSON file. It is divided into several top-level sections:

- `metadata`: General information about the simulation.
- `components`: Definitions of chemical components.
- `properties`: Property method settings.
- `blocks`: Unit operation definitions.
- `streams`: Feed stream definitions.
- `flowsheet`: Connectivity of blocks and streams.
- `chemistry`: (Optional) Reaction definitions.

## Sections

### Metadata

Contains global settings for the simulation.

**Fields:**
- `title` (required): Name of the simulation.
- `units` (required): Default units for the simulation.
    - `pressure`: One of `bar`, `psi`, `atm`, `kPa`, `MPa`.
    - `temperature`: One of `C`, `F`, `K`, `R`.
    - `flow`: One of `kg/hr`, `kmol/hr`, `lb/hr`, `lbmol/hr`.

**Example:**
```yaml
metadata:
  title: "Methanol Plant"
  units:
    pressure: "bar"
    temperature: "C"
    flow: "kmol/hr"
```

### Components

List of chemical components used in the simulation.

**Fields:**
- `id` (required): Unique identifier for the component (e.g., "H2O").
- `name` (required): Full name or alias of the component (e.g., "WATER").

**Example:**
```yaml
components:
  - id: "H2O"
    name: "WATER"
  - id: "ET-OH"
    name: "ETHANOL"
```

### Properties

Global property method settings.

**Fields:**
- `method`: The property method to use (e.g., "NRTL", "RK-SOAVE").

**Example:**
```yaml
properties:
  method: "NRTL"
```

### Blocks

Definitions of unit operation blocks.

**Fields:**
- `name` (required): Unique name of the block.
- `type` (required): Type of the block (e.g., "MIXER", "FLASH2").

**Example:**
```yaml
blocks:
  - name: "MIX-01"
    type: "MIXER"
```

### Streams

Definitions of material streams, primarily feed streams.

**Fields:**
- `name` (required): Unique name of the stream.
- `temperature` (required): Temperature value.
- `pressure` (required): Pressure value.
- `mole_flow` OR `mass_flow`: Flow rate.
- `composition` (optional): Dictionary mapping component IDs to mole/mass fractions.

**Example:**
```yaml
streams:
  - name: "FEED"
    temperature: 25
    pressure: 1.01325
    mole_flow: 100
    composition:
      H2O: 0.5
      ET-OH: 0.5
```

### Flowsheet

Refines the connectivity of the process.

**Fields:**
- `block` (required): Name of the block.
- `inputs` (required): List of input stream names.
- `outputs` (required): List of output stream names.

**Example:**
```yaml
flowsheet:
  - block: "MIX-01"
    inputs: ["FEED1", "FEED2"]
    outputs: ["PRODUCT"]
```

## Validation Rules

The `aspen_automation` package enforces several validation rules when loading a specification:

1.  **Structure**: All required top-level sections must be present.
2.  **Types**: Fields must be of the correct data type (number, string, list, dict).
3.  **Required Fields**: Essential fields (like `id`, `name`, `type`) must be defined.
4.  **Units**: Units must be one of the supported values.
5.  **References**:
    -   Components referenced in streams/reactions must be defined in `components`.
    -   Blocks referenced in `flowsheet` must be defined in `blocks`.
    -   Streams referenced in `flowsheet` inputs/outputs must be defined in `streams`.
6.  **Composition**: Mole/mass fractions in a stream must sum to approximately 1.0 (tolerance: 0.1%).

## API Usage

### Python

```python
from aspen_automation import load_spec, ValidationError

try:
    spec = load_spec("plant.yaml")
    print(f"Loaded spec: {spec['metadata']['title']}")
except ValidationError as e:
    print("Validation failed:")
    for error in e.report["errors"]:
        print(f"- {error['location']}: {error['message']}")
        if "suggestion" in error:
            print(f"  Suggestion: {error['suggestion']}")
except Exception as e:
    print(f"Error: {e}")
```

### Validation Only

```python
from aspen_automation import load_spec, validate_spec

# Load without validation
spec = load_spec("plant.yaml", validate=False)

# Validate manually
report = validate_spec(spec)
if not report["valid"]:
    print("Errors found:", report["errors"])
```
