
# Implementation Plan: Robust Stream Export

## Objective
Export simulation results from `automatedmixer.bkp` to `streams.csv` while ensuring the automation script never hangs ("stacks").

## The Problem
Running `aspen.Engine.Run2()` without arguments is **synchronous**. It waits for Aspen to finish. If Aspen opens a dialog, waits for user input, or crashes silently, the Python script waits forever.

## The Solution
1. **Asynchronous Execution**: Use `Engine.Run2(1)`. This forces Aspen to run in the background and returns control to Python immediately.
2. **Polling Loop**: Python will check `Engine.IsRunning` every second.
3. **Timeout Safety**: If the simulation takes longer than X seconds (e.g., 60s), Python will abort, ensuring the agent doesn't hang.
4. **Hard Cleanup**: Use `Quit()` and ensuring the process is terminated.

## Script Logic (robust_export.py)
1. **Load**: `InitFromArchive2("automatedmixer.bkp")`
2. **Run**: 
   - Call `Engine.Run2(1)`
   - While `Engine.IsRunning` == 1:
     - Sleep 1s
     - Check timeout
3. **Export**:
   - Navigate to `\Data\Streams`
   - Iterate all streams
   - For each stream, fetch: TEMP, PRES, MASSFLOW (and potential composition)
   - Write to `streams.csv`
4. **Close**: `aspen.Close()` or `aspen.Quit()`

## Output Format (streams.csv)
```csv
StreamName, Temperature (C), Pressure (bar), MassFlow (kg/hr), Status
WATER1, 25.0, 1.0, 1000.0, Valid
OUT, 25.0, 1.0, 2000.0, Valid
```
