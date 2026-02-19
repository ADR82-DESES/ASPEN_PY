# API Usage Guide

This guide demonstrates how to use the `aspen_automation` package to load, validate, and manipulate Aspen Plus plant specifications.

## Basic Usage

The primary entry point is the `load_spec` function, which handles file reading, format detection (YAML/JSON), and full validation.

```python
from aspen_automation import load_spec

# Load and validate a YAML specification
try:
    spec = load_spec("specs/methanol_plant.yaml")
    print(f"Successfully loaded: {spec.metadata.title}")
    
    # Access data using dot notation
    for stream in spec.streams:
        print(f"Stream {stream.name}: {stream.temperature} {spec.metadata.units.temperature}")
        
except Exception as e:
    print(f"Failed to load spec: {e}")
```

## INP Generation

The package can generate Aspen Plus Input (`.inp`) files from a validated specification.

```python
from aspen_automation import load_spec, generate_inp

spec = load_spec("specs/methanol_plant.yaml")
inp_content = generate_inp(spec, output_path="MethanolPlant_Generated.inp")
```

See the [INP Generation Guide](INP_GENERATION.md) for detailed information on output formats and unit mapping.

## Advanced Validation

If you already have a dictionary and want to validate it without loading from a file, use `validate_spec`.

```python
from aspen_automation import validate_spec

raw_data = {
    "metadata": {
        "title": "Quick Test",
        "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}
    },
    # ... other fields ...
}

report = validate_spec(raw_data)

if report["valid"]:
    print("Specification is valid!")
else:
    print(f"Found {len(report['errors'])} issues:")
    for error in report["errors"]:
        print(f"- {error['location']}: {error['message']}")
```

## Handling Validation Errors

When `load_spec` fails validation, it raises a custom `ValidationError` containing a detailed report.

```python
from aspen_automation import load_spec, ValidationError

try:
    spec = load_spec("invalid_config.yaml")
except ValidationError as e:
    # Print the formatted error message
    print(e)
    
    # Or access the raw report for programmatic handling
    for error in e.errors:
        if error["severity"] == "error":
            print(f"Fix required at {error['location']}: {error['message']}")
```

## Specification Examples

### YAML Example (`plant.yaml`)

```yaml
metadata:
  title: "Simple Mixer"
  units:
    pressure: "bar"
    temperature: "C"
    flow: "kg/hr"

components:
  - id: "H2O"
    name: "WATER"

properties:
  method: "STEAM-TA"

flowsheet:
  - block: "MIX1"
    inputs: ["FEED"]
    outputs: ["PROD"]

streams:
  - name: "FEED"
    temperature: 25.0
    pressure: 1.0
    mass_flow: 1000.0
    composition:
      H2O: 1.0

blocks:
  - name: "MIX1"
    type: "MIXER"
```

### JSON Example (`plant.json`)

```json
{
  "metadata": {
    "title": "Simple Mixer",
    "units": {
      "pressure": "bar",
      "temperature": "C",
      "flow": "kg/hr"
    }
  },
  "components": [
    { "id": "H2O", "name": "WATER" }
  ],
  "properties": {
    "method": "STEAM-TA"
  },
  "flowsheet": [
    { "block": "MIX1", "inputs": ["FEED"], "outputs": ["PROD"] }
  ],
  "streams": [
    {
      "name": "FEED",
      "temperature": 25.0,
      "pressure": 1.0,
      "mass_flow": 1000.0,
      "composition": { "H2O": 1.0 }
    }
  ],
  "blocks": [
    { "name": "MIX1", "type": "MIXER" }
  ]
}
```
