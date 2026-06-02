# Aspen Plus Automation API

This package provides a schema-first approach to defining and validating Aspen Plus chemical process simulations.

## Features

- **Validation-First**: Catch errors before running expensive simulations.
- **Cross-Reference Checking**: Ensures all streams, blocks, and components are correctly wired.
- **Chemistry & Targets**: Support for reaction stoichiometry and production targets.
- **Support for YAML/JSON**: Human-readable specification formats.
- **Pydantic-Powered**: Robust type checking and serialization.

## Quick Start

```python
from aspen_automation import load_spec, generate_inp

# Load and validate
spec = load_spec("plant.yaml")

# Access data with dot notation
print(spec.metadata.title)
for stream in spec.streams:
    print(f"Stream {stream.name}: {stream.temperature} {spec.metadata.units.temperature}")
```

## INP Generation

```python
from aspen_automation import load_spec, generate_inp

spec = load_spec("plant.yaml")
inp_content = generate_inp(spec, output_path="plant.inp")
```

## Loading INP via Aspen Plus COM

```python
import os
import win32com.client as win32

inp_path = os.path.abspath("plant.inp")
aspen = win32.Dispatch("Apwn.Document")
aspen.SuppressDialogs = 1
aspen.InitFromFile2(inp_path)
```

## Validation Rules
The package implements comprehensive checks for:
- Component definition coverage
- Stream connectivity (flowsheet vs streams section)
- Block connectivity (flowsheet vs blocks section)
- Composition sum (must be 1.0)
- Unit systems compatibility
- Typed fields (numeric/string/list/dict)

## Documentation
Full documentation is available in the `docs` directory:
- [API Usage Guide](../docs/API_USAGE.md)
- [Validation Rules](../docs/VALIDATION_RULES.md)
- [Schema Reference](../docs/SCHEMA_REFERENCE.md)
