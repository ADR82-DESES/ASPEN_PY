# Skill: Aspen Plus Automation (Python/COM)

This document provides essential patterns, code snippets, and troubleshooting steps for automating Aspen Plus using Python and the Win32 COM Interface (`pywin32`).

## Core Principles

1.  **Initialization is Mandatory**: The COM object (`Apwn.Document`) must be initialized using `InitNew()` or `InitFromArchive2(path)` before the Variable Tree (`aspen.Tree`) becomes accessible.
2.  **Hybrid Approach**: For maximum reliability, create the flowsheet (blocks and stream connections) manually in the Aspen Plus GUI, then use Python to automate inputs, execution, and result extraction.
3.  **Absolute Paths**: Always use `os.path.abspath()` when passing file paths to Aspen COM methods.

## Connection & Initialization

### Standard Connection Boilerplate
Always suppress dialogs to prevent the script from hanging on background popups.

```python
import os
import win32com.client as win32

def connect_to_aspen(filepath=None, visible=True):
    """Connects to Aspen Plus and initializes the document."""
    aspen = win32.Dispatch('Apwn.Document')
    aspen.Visible = visible
    aspen.SuppressDialogs = 1
    
    if filepath:
        full_path = os.path.abspath(filepath)
        # InitFromArchive2 is preferred for .bkp and .apw files
        aspen.InitFromArchive2(full_path)
    else:
        # Must initialize even for a blank simulation
        aspen.InitNew()
        
    return aspen
```

## Tree Navigation Reference

The `aspen.Tree.FindNode(path)` method is the primary way to interact with simulation data.

### Material Streams
- **Temperature**: `\Data\Streams\{ID}\Input\TEMP\MIXED`
- **Pressure**: `\Data\Streams\{ID}\Input\PRES\MIXED`
- **Mass Flow**: `\Data\Streams\{ID}\Input\MASSFLMX\MIXED`
- **Composition (Mole Frac)**: `\Data\Streams\{ID}\Input\MOLEFRAC\MIXED\{COMP_ID}`

### Result Extraction (Output)
- **Outlet Temperature**: `\Data\Streams\{ID}\Output\TEMP_OUT\MIXED`
- **Outlet Pressure**: `\Data\Streams\{ID}\Output\PRES_OUT\MIXED`
- **Outlet Mass Flow**: `\Data\Streams\{ID}\Output\MASSFLMX\MIXED`
- **Block Duty**: `\Data\Blocks\{ID}\Output\QNET` (or `DUTY`)

## Workflow Automation

### Running the Simulation
```python
# Run the simulation engine
aspen.Engine.Run2()

# Check for convergence errors
errors = aspen.Tree.FindNode(r"\Data\Results Summary\Run-Status\Output\NERROR").Value
warnings = aspen.Tree.FindNode(r"\Data\Results Summary\Run-Status\Output\NWARN").Value

if errors > 0:
    print(f"Simulation failed with {errors} errors.")
```

### Saving Results
```python
# Save changes to the current file
aspen.Save()

# Save as a new file
aspen.SaveAs(os.path.abspath("new_version.bkp"))
```

## Common Gotchas & Troubleshooting

### "Application has not been initialized"
- **Cause**: Attempting to access `aspen.Tree` or `aspen.Engine` before calling `InitNew()` or `InitFromArchive2()`.
- **Solution**: Ensure initialization happens immediately after `Dispatch`.

### "NoneType object has no attribute 'Value'"
- **Cause**: The path provided to `FindNode()` does not exist in the current flowsheet.
- **Solution**: Verify the path in the Aspen Plus "Variable Explorer". Remember that paths are case-sensitive and often require trailing identifiers like `\MIXED`.

### Script Hangs
- **Cause**: A popup dialog is waiting for user input in a hidden Aspen instance.
- **Solution**: Set `aspen.Visible = True` during debugging and always set `aspen.SuppressDialogs = 1` in production.

### "Property or method may not be executed"
- **Cause**: COM security restrictions or attempting to write to a "Read-Only" result node.
- **Solution**: Ensure you are writing to `Input` nodes and reading from `Output` nodes.
