# Notebook Diagnostic Report
**Date:** 2026-05-06  
**Notebook:** `notebooks/process_library_runner.ipynb`  
**Run method:** `jupyter nbconvert --execute` (non-interactive, 60 s kernel timeout)

---

## Overall Result: PARTIAL PASS

| Layer | Status | Notes |
|-------|--------|-------|
| Notebook execution (Python) | PASS | All 11 cells executed, no Python exceptions |
| Imports & environment | PASS | All `aspen_automation` symbols imported correctly |
| Path resolution | PASS | Repo root, process library, and runs directories resolved |
| Process discovery | PASS | 1 process found: `methanol` |
| YAML schema validation | PASS | `process.yaml` is structurally valid |
| Coherence analysis | PASS | Coherence gate passed, no blocking issues |
| YAML improvement suggestions | PASS | Suggestions generated, no mandatory edits required |
| **Aspen Plus COM build** | **FAIL** | Missing localization assembly (see below) |
| Results extraction | SKIPPED | Blocked by build failure |
| Codex session analysis | SKIPPED | Blocked by build failure |

---

## Root Cause: Missing Aspen Plus Localization Assembly

**Error message:**
```
COM block builder failed: Unable to create block 'MIX-FEED' as 'MIXER'.
Last error: (-2147352567, 'Ocurrió una excepción.',
  (0, 'PresentationFramework',
   "No se puede cargar el archivo o ensamblado
    'AspenTech.AspenPlus.Localization, PublicKeyToken=null'
    ni una de sus dependencias.
    El sistema no puede encontrar el archivo especificado.",
   None, 0, -2146233087), None)
```

**Translation (error is in Spanish):**  
*"Cannot load the file or assembly 'AspenTech.AspenPlus.Localization, PublicKeyToken=null' or one of its dependencies. The system cannot find the file specified."*

**What this means:**  
When the COM builder tries to create the first flowsheet block (`MIX-FEED` of type `MIXER`), Aspen Plus loads its UI/localization layer via `PresentationFramework` (WPF), which in turn tries to load `AspenTech.AspenPlus.Localization.dll`. That DLL is missing from the installation.

---

## Likely Causes

1. **Incomplete Aspen Plus installation** — The localization package was not installed or was installed for a different locale. This is common when Aspen Plus is installed with a minimal/custom setup.

2. **Version mismatch** — The registered COM server points to one version of Aspen Plus, but the localization DLL belongs to a different version or path.

3. **Corrupted installation** — The DLL exists but is corrupt or blocked by Windows (e.g., downloaded and not unblocked).

4. **Missing Visual C++ / .NET runtime** — The assembly's dependencies (Visual C++ redistributable, specific .NET version) may not be installed.

---

## Recommended Fixes

### Fix 1: Repair Aspen Plus installation (most likely fix)
Open **Control Panel → Programs → Aspen Plus → Change → Repair**.  
This reinstalls missing files including localization packages.

### Fix 2: Check that the localization DLL exists
Search for the file manually:
```powershell
Get-ChildItem "C:\Program Files (x86)\AspenTech" -Recurse -Filter "AspenTech.AspenPlus.Localization.dll" -ErrorAction SilentlyContinue
Get-ChildItem "C:\Program Files\AspenTech" -Recurse -Filter "AspenTech.AspenPlus.Localization.dll" -ErrorAction SilentlyContinue
```
If not found, the localization package was not installed.

### Fix 3: Verify the COM registration points to the correct installation
```powershell
Get-ItemProperty "HKLM:\SOFTWARE\Classes\Apwn.Document\CLSID" -ErrorAction SilentlyContinue
```
The CLSID should match the installed version.

### Fix 4: Unblock DLLs downloaded from the internet
If Aspen Plus was installed from a downloaded package, right-click the installer → Properties → Unblock, then reinstall.

---

## What Works Without Aspen Plus

The following parts of the notebook are fully functional and can be used without Aspen Plus:

- **YAML spec discovery** (`scan_process_library`)
- **YAML validation** (`validate_process_spec_file`)
- **Coherence analysis** (`analyze_process_spec_coherence`)
- **Improvement suggestions** (`suggest_process_spec_improvements`)
- **INP file generation** (`generate_inp`) — the `.inp` file was generated successfully

The generated INP file is at:
```
process_runs/methanol/run_<timestamp>/methanol_generated.inp
```

---

## Next Steps

1. Repair or reinstall Aspen Plus, focusing on the localization/language pack component.
2. After repair, re-run: `pixi run python run_minimal.py` as a quick smoke test before re-running the full notebook.
3. If Aspen Plus is not available on this machine, the notebook can still be used up to and including Step 8 (coherence + YAML improvement) for spec authoring and validation workflows.
