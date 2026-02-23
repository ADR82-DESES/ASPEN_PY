# Session Management

## Overview

The `aspen_automation.session` module provides a robust interface for orchestrating Aspen Plus simulations. It handles connection management, file generation, simulation execution, and result collection.

## Build Modes

| Mode | Description | Mechanism |
| :--- | :--- | :--- |
| `auto` | Default. Tries `InitFromFile2`, falls back to `InitNew` + `Import`. | Hybrid |
| `inp-only` | Generates INP and uses `InitFromFile2`. | File-based |
| `com-only` | Uses direct COM manipulation (Diagnostic). | COM (Diagnostic/dev, implemented) |

## Auto Fallback Logic

```mermaid
graph TD
    A[Start Build Auto] --> B{InitFromFile2 Success?}
    B -- Yes --> C[Use InitFromFile2]
    B -- No --> D[InitNew]
    D --> E{Import Method?}
    E -- Import --> F[Use aspen.Import]
    E -- ImportSimulation --> G[Use aspen.ImportSimulation]
    F --> H[Success]
    G --> H
    E -- Failure --> I[BuildError]
```

## API Reference

### `run_simulation_session`

Orchestrates the entire session.

**Signature:**

```python
def run_simulation_session(
    spec: Union[PlantSpecification, Dict[str, Any]], 
    build_mode: str = "auto",
    output_dir: str = "results/",
    visible: bool = True,
    timeout_seconds: int = 300,
    keep_alive: bool = False,
    raise_on_connection_error: bool = False
) -> SessionResult
```

**Parameters:**

| Name | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `spec` | `Union[PlantSpecification, Dict[str, Any], str]` | - | Specification model, raw dict, or file path. |
| `build_mode` | `str` | `"auto"` | One of `"auto"`, `"inp-only"`, `"com-only"`. |
| `output_dir` | `str` | `"results/"` | Directory for intermediate/output artifacts. |
| `visible` | `bool` | `True` | Whether Aspen UI is visible. |
| `timeout_seconds` | `int` | `300` | Maximum simulation runtime before timeout. |
| `keep_alive` | `bool` | `False` | If `True`, keeps Aspen session open and preserves `aspen` object. |
| `raise_on_connection_error` | `bool` | `False` | If `True`, re-raises `AspenConnectionError` instead of soft-failing. |

### `SessionResult`

Data class containing simulation results.

**Fields:**

- `convergence_status` (str): `"converged"`, `"failed"`, `"timeout"`, or `"unknown"`.
- `build_mode` (str): Mode used ("auto", "inp-only", "com-only").
- `build_mechanism_used` (str): Mechanism that succeeded ("InitFromFile2", "Import", etc.).
- `build_fallback_attempted` (bool): Whether fallback was triggered in auto mode.
- `simulation_time_seconds` (float): Duration of the simulation.
- `diagnostics` (Dict[str, Any]): Logs and error/context values.
- `aspen` (Any): COM object reference (if `keep_alive=True`).

## COM Limitations

- `win32com.client` must be available (Windows only).
- `AspenConnectionError` is raised if connection fails or library is missing.

## Pipeline Integration

Use `run_simulation_session` in compliant CI/CD pipelines to validate plant specifications automatically.

## Troubleshooting

- **ImportError**: Ensure `pywin32` is installed.
- **AspenConnectionError**: Check if Aspen Plus is installed and license is active.
- **BuildError**: Verify INP generation syntax and file permissions.
- **SimulationError**: Check simulation timeout and convergence parameters.
