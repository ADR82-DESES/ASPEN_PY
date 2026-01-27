
# Implementation Plan - Water Mixer Simulation (Aspen Plus via COM)

This plan outlines the steps to automate an Aspen Plus simulation to mix two water streams using the Python `win32com` interface.

## User Review Required

> [!IMPORTANT]
> **No Official PyPI Package**: There is no official "Aspen Plus" package on PyPI. The standard industry method is using the **COM Interface** via `pywin32`.
> **Prerequisites**: You must have Aspen Plus installed on this machine.
> **Simulation File**: This script assumes we are connecting to an existing Aspen Plus simulation or template. If you do not have one, the script can attempt to open a blank simulation, but defining strict chemistry/components from scratch via COM is complex.

## Proposed Changes

### Dependencies
- Add `pywin32` using `uv`.

### New Files
- `aspen_mixer_automation.py`:
    - Connects using `InitNew` if needed.
    - **Setup**: Defines "WATER" component and "IDEAL" property method.
    - **Build**: Creates "MIXER" block and streams ("WATER1", "WATER2", "OUT") if missing.
    - **Connect**: Connects streams to Mixer input/output ports.
    - **Run**: Sets inputs and runs simulation.
    - **Export**: Writes mass flow, temp, pressure to `results.csv`.

## Verification Plan

### Automated Tests
- The script will include checks to verify COM connection is successful.
- It will assert that the simulation converges (Run Status).

### Manual Verification
- Run `uv run aspen_mixer_automation.py`.
- Verify that Aspen Plus opens (or runs in background) and the results match expected heat/mass balance.
