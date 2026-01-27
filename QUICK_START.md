# QUICK START GUIDE - Complete the Simulation

## Current Status

✅ **What the script did successfully:**
- Connected to Aspen Plus
- Initialized new simulation
- Added WATER component (implied)
- Created 3 streams: WATER1, WATER2, OUT

❌ **What needs manual completion:**
- Add MIXER block
- Connect streams to MIXER
- Set stream specifications

## 🎯 Complete These Steps in Aspen Plus GUI:

### Step 1: Add Component (if not already done)
1. Go to **Setup → Components → Specifications**
2. In the **Component ID** field, type: `WATER`
3. Press Enter (Aspen will auto-fill it as H2O)

### Step 2: Set Property Method
1. Go to **Setup → Properties → Specifications**
2. Select **IDEAL** as the Base method
3. Click **Next** until you reach the main flowsheet

### Step 3: Add MIXER Block
1. In the **Model Palette** (left side), find **Mixers/Splitters**
2. Drag **Mixer** onto the flowsheet
3. When prompted for a name, enter: `MIXER`
4. Click **OK**

### Step 4: Connect Streams
You should see three streams already created: WATER1, WATER2, OUT

1. **Connect WATER1 to MIXER:**
   - Click on WATER1 stream
   - Drag the red arrow to the MIXER inlet

2. **Connect WATER2 to MIXER:**
   - Click on WATER2 stream
   - Drag the red arrow to the MIXER inlet

3. **Connect OUT from MIXER:**
   - Click on OUT stream
   - Drag the blue arrow from MIXER outlet to the stream

### Step 5: Specify Input Streams

**For WATER1 (hot water):**
1. Double-click the WATER1 stream
2. Go to the **Input** tab
3. Enter:
   - Temperature: `80` °C
   - Pressure: `2` bar
   - Total Flow: `1000` kg/hr
   - Composition: `1.0` for WATER

**For WATER2 (cold water):**
1. Double-click the WATER2 stream
2. Go to the **Input** tab
3. Enter:
   - Temperature: `20` °C
   - Pressure: `2` bar
   - Total Flow: `1000` kg/hr
   - Composition: `1.0` for WATER

### Step 6: Save the Simulation
1. Click **File → Save As**
2. Save as: `MixerSimulation.bkp`
3. Save location: `C:\Users\domingueza\ASPEN_PY\`

## ✅ After Manual Setup is Complete:

### Option 1: Run from GUI
Just click the **Run** button (▶) in Aspen Plus

### Option 2: Run from Python
Use the simple automation script:

```bash
uv run python simple_run.py
```

This will:
- Connect to your open simulation
- Verify inputs are set
- Run the simulation
- Extract results to `results.csv`

## 📊 Expected Results:

**Outlet Stream (OUT):**
- Temperature: ~50°C (average of 80°C and 20°C)
- Pressure: 2 bar
- Mass Flow: 2000 kg/hr (sum of both inlets)

## 🔄 For Future Runs:

Once you have `MixerSimulation.bkp` saved, you can fully automate:

```bash
uv run python final_solution.py
```

Choose option **B** and load `MixerSimulation.bkp`

The script will then:
1. Load your saved simulation
2. Modify input parameters (if needed)
3. Run the simulation
4. Extract results automatically

---

**Current Action:** The script is waiting for your input (y/n to run simulation).

**Recommendation:** Type `n` for now, complete the manual setup above, then use `simple_run.py` for automation.
