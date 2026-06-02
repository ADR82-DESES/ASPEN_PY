"""
SOLUTION: Create a Template File Programmatically
Since we can't add blocks via COM, we'll create a minimal .bkp file with a mixer
that can be loaded and modified programmatically
"""
import win32com.client as win32
import os
import sys

print("="*70)
print("CREATING ASPEN PLUS MIXER TEMPLATE")
print("="*70)

# Step 1: Connect
print("\n[1] Connecting to Aspen Plus...")
try:
    aspen = win32.Dispatch("Apwn.Document")
    print("[OK] Connected")
except Exception as e:
    print(f"[FAIL] {e}")
    sys.exit(1)

# Step 2: Initialize
print("\n[2] Initializing new simulation...")
try:
    aspen.InitNew()
    aspen.Visible = True
    print("[OK] Initialized")
except Exception as e:
    print(f"[FAIL] {e}")
    sys.exit(1)

# Step 3: Add what we CAN add programmatically
print("\n[3] Adding Components...")
try:
    # Wait a moment for tree to be ready
    import time
    time.sleep(2)
    
    comp_node = aspen.Tree.FindNode(r"\Data\Components\Specifications\Input\CAG_IDS")
    if comp_node:
        comp_node.Elements.Add("WATER")
        print("[OK] WATER component added")
    else:
        print("[WARN] Components node not found - tree may not be fully initialized")
except Exception as e:
    print(f"[INFO] {e}")

# Step 4: Set property method
print("\n[4] Setting Property Method...")
try:
    method_node = aspen.Tree.FindNode(r"\Data\Properties\Global\Input\METHOD")
    if method_node:
        method_node.Value = "IDEAL"
        print("[OK] Property method set to IDEAL")
except Exception as e:
    print(f"[INFO] {e}")

# Step 5: Create streams
print("\n[5] Creating Streams...")
try:
    streams = aspen.Tree.FindNode(r"\Data\Streams")
    if streams:
        for stream in ["WATER1", "WATER2", "OUT"]:
            try:
                streams.Elements.Add(stream)
                print(f"[OK] {stream}")
            except:
                print(f"[INFO] {stream} may already exist")
except Exception as e:
    print(f"[WARN] {e}")

# Step 6: Save this partial simulation
print("\n[6] Saving partial simulation...")
template_path = os.path.abspath("MixerTemplate_Partial.bkp")
try:
    aspen.SaveAs(template_path)
    print(f"[OK] Saved to: {template_path}")
except Exception as e:
    print(f"[FAIL] {e}")

# Step 7: Instructions
print("\n" + "="*70)
print("NEXT STEPS - MANUAL COMPLETION REQUIRED")
print("="*70)
print(f"""
The file has been saved to:
{template_path}

TO COMPLETE THE TEMPLATE:
1. In the Aspen Plus window that just opened:
   - Go to the flowsheet view
   - From the Model Palette, drag a MIXER block onto the flowsheet
   - Name it: MIXER
   - Connect WATER1 to MIXER input
   - Connect WATER2 to MIXER input  
   - Connect OUT to MIXER output

2. Save the file (Ctrl+S or File -> Save)

3. Close Aspen Plus

4. Run this command:
   uv run python use_template.py

This will load your template and run fully automated simulations!

ALTERNATIVE - If you absolutely cannot do manual steps:
The only way to achieve 100% automation without ANY manual steps is to:
- Use Aspen Plus Simulation Engine (APWN) with pre-made simulation files
- Use a different Aspen Plus API (if available for your version)
- Use UI automation tools (pyautogui, etc.) to simulate mouse/keyboard
- Contact AspenTech support for programmatic block creation methods

The COM interface limitation appears to be:
- Blocks require a Model Library to be loaded
- The library loading mechanism isn't exposed via COM
- This is likely a design decision by AspenTech
""")

print("="*70)
