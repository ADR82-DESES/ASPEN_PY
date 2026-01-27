# Aspen Plus Automation Guide

## Current Status

The Python scripts are successfully connecting to Aspen Plus via COM, but encountering issues when trying to manipulate the flowsheet programmatically. The error "property or method may be executed" suggests COM security restrictions.

## The Problem

Based on your feedback:
1. ✅ Aspen Plus is running
2. ✅ Python can connect via COM (`win32.Dispatch("Apwn.Document")`)
3. ❌ The flowsheet remains empty after running the script
4. ❌ Status shows "Flowsheet not complete"

## Root Cause

The COM interface has limitations when trying to create flowsheet elements programmatically on a completely blank document. The recommended approach is:

**Manual Setup + Automated Execution**

## Recommended Solution

### Option 1: Manual Flowsheet Creation (RECOMMENDED)

1. **In Aspen Plus, create the flowsheet manually:**
   - File → New → Blank Simulation
   - Setup → Components → Add "WATER"
   - Setup → Properties → Select "IDEAL" method
   - Drag a Mixer block onto the flowsheet, name it "MIXER"
   - Create 3 material streams: WATER1, WATER2, OUT
   - Connect WATER1 and WATER2 to MIXER inputs
   - Connect OUT to MIXER output
   - Save as `MixerSimulation.bkp`

2. **Then run the Python script to:**
   - Load the saved file
   - Set input conditions (temperatures, pressures, flows)
   - Run the simulation
   - Extract and save results

### Option 2: Use Aspen Plus Templates

Aspen Plus comes with templates that can be loaded programmatically. However, this requires knowing the exact template path.

### Option 3: Create from Existing File

If you have an existing Aspen Plus simulation file, the script can:
- Load it
- Modify parameters
- Run it
- Extract results

## Next Steps

**Please choose one of the following:**

### A. Manual Setup (Easiest)
Follow the steps in Option 1 above, then run:
```bash
uv run python run_mixer_sim.py
```

### B. Provide an Existing File
If you have an existing Aspen Plus simulation file (.bkp or .apw), place it in this directory and I'll modify the script to use it.

### C. Alternative Approach
Use Aspen Plus's built-in automation features:
- Excel integration
- Aspen Plus Simulation Engine (APWN) with pre-configured files
- Aspen Plus Dynamics

## Technical Details

The COM interface (`Apwn.Document`) works best when:
1. A simulation file is already loaded
2. The flowsheet structure exists
3. We're modifying existing parameters rather than creating new elements

Creating elements from scratch via COM is possible but requires:
- Exact knowledge of the tree structure
- Proper initialization sequences
- Sometimes administrator privileges
- Specific Aspen Plus version compatibility

## Files in This Project

- `aspen_mixer_automation.py` - Original automation script
- `run_mixer_sim.py` - Script with instructions for manual setup
- `test_connection.py` - Connection diagnostic tool
- `results.csv` - Output results file

## Support

If you continue to have issues, please provide:
1. Your Aspen Plus version
2. Whether you're running as administrator
3. Any error messages from Aspen Plus itself (not just Python)
