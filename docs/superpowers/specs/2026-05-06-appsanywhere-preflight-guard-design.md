# Design: AppsAnywhere Pre-flight Guard

**Date:** 2026-05-06  
**Status:** Approved  
**Scope:** `aspen_automation/exceptions.py`, `aspen_automation/session.py`, `aspen_automation/__init__.py`, `notebooks/process_library_runner.ipynb`

---

## Problem

Aspen Plus at Universidad de Cantabria is delivered via **AppsAnywhere** (Porticada portal), not installed locally. The COM server (`Apwn.Document`) is only registered in the Windows registry while Aspen is actively running from the portal.

When the Python codebase calls `run_simulation_session()` without Aspen pre-launched, `_connect_aspen()` tries to start a new Aspen process. This fails with a cryptic COM error:

```
No se puede cargar el archivo o ensamblado
'AspenTech.AspenPlus.Localization, PublicKeyToken=null'
```

The real cause — Aspen is not running — is not surfaced to the user.

**Verified:** When Aspen 14 is launched from Porticada first, `win32com.client.GetActiveObject("Apwn.Document")` succeeds and `win32com.client.Dispatch("Apwn.Document")` connects cleanly. The full COM automation pipeline works.

---

## Solution: Pre-flight Guard (Approach A)

A minimal, surgical change: check whether Aspen is already running before attempting any COM interaction. If not running, raise a clear, actionable error.

No changes to the COM flow, build logic, or simulation pipeline.

---

## Architecture

### Files changed

| File | Change |
|------|--------|
| `aspen_automation/exceptions.py` | Add `AspenNotRunningError` |
| `aspen_automation/session.py` | Add `check_aspen_running()` + inject guard into `run_simulation_session()` |
| `aspen_automation/__init__.py` | Export `check_aspen_running` and `AspenNotRunningError` |
| `notebooks/process_library_runner.ipynb` | New pre-flight cell (section 1.5) |

### Call chain (unchanged except for the guard)

```
run_simulation_session()
  ├── [NEW] check_aspen_running()  →  raises AspenNotRunningError if False
  └── _connect_aspen()             →  win32.Dispatch("Apwn.Document")
        └── build_flowsheet_via_com() / INP import
              └── simulation run + extraction
```

---

## Component Specifications

### 1. `AspenNotRunningError` — `exceptions.py`

Subclass of `AspenConnectionError` so existing `except AspenConnectionError` blocks continue to catch it without modification.

```python
class AspenNotRunningError(AspenConnectionError):
    def __init__(self):
        super().__init__(
            "Aspen Plus is not running. "
            "Please launch Aspen 14 from the Porticada portal "
            "(https://porticada.unican.es) and try again."
        )
```

**Invariants:**
- No parameters — the message is always the same.
- Inherits `details` attribute from `AspenConnectionError` (defaults to `None`).

### 2. `check_aspen_running()` — `session.py`

Public utility function. Uses `GetActiveObject` (not `Dispatch`) so it never launches a new Aspen process as a side effect.

```python
def check_aspen_running() -> bool:
    """Returns True if Aspen Plus is currently running and reachable via COM."""
    if win32 is None:
        return False
    try:
        win32.GetActiveObject(ASPEN_DOCUMENT_PROG_ID)
        return True
    except Exception:
        return False
```

**Invariants:**
- Never raises — always returns `bool`.
- Returns `False` on non-Windows (where `win32` is `None`).
- Uses the existing `ASPEN_DOCUMENT_PROG_ID = "Apwn.Document"` constant.

### 3. Guard injection — `run_simulation_session()`

Inserted immediately before the `aspen = _connect_aspen()` call (currently line 1600), inside the `try` block, after spec validation and output directory setup:

```python
if not check_aspen_running():
    raise AspenNotRunningError()
```

**Why here:** After spec/mode validation (so spec errors are reported first) but before any COM interaction (so the guard fires before the cryptic error).

### 4. `__init__.py` exports

```python
from .session import check_aspen_running, check_aspen_v14_connection, run_simulation_session, SessionResult
from .exceptions import (
    ValidationError, ParserError, SchemaError, ExtractionError,
    AspenConnectionError, AspenNotRunningError, BuildError, SimulationError
)
```

### 5. Notebook pre-flight cell — `process_library_runner.ipynb`

New cell inserted between existing **Section 1** (imports) and **Section 2** (path resolution), with markdown header `## 1.5 Aspen Plus pre-flight check`:

```python
from aspen_automation import check_aspen_running
from aspen_automation.exceptions import AspenNotRunningError

if not check_aspen_running():
    raise AspenNotRunningError()

print("Aspen Plus is running. Ready to proceed.")
```

The cell raises immediately if Aspen is not running, preventing the notebook from reaching the simulation cell (step 9) where the error would otherwise surface after significant delay.

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Aspen not running, `run_simulation_session()` called | `AspenNotRunningError` raised immediately with portal URL |
| Aspen not running, notebook executed | Cell 1.5 raises `AspenNotRunningError`, notebook stops |
| `win32com` not installed (non-Windows) | `check_aspen_running()` returns `False`, same error raised |
| Aspen running, COM connect fails for other reason | Falls through to existing `AspenConnectionError` handling |

---

## User Workflow (after this change)

1. Open browser → Porticada portal → launch **Aspen 14**
2. Wait for Aspen Plus to fully load
3. Open `notebooks/process_library_runner.ipynb` and run the preflight/Gate 1 cells
4. Simulation proceeds normally

---

## Out of Scope

- Automatically launching Aspen from Python (would require local installation)
- A `connect_mode="attach"` parameter (Approach B — deferred)
- Changes to `com_builder.py`, `runner.py`, or any other module
- Any change to how the simulation itself runs once connected
