"""
Methanol Plant Flowsheet Builder - UI Automation
=================================================
Uses pyautogui and pywinauto to automate the Aspen Plus GUI
for creating blocks (since COM cannot create blocks).

IMPORTANT: 
- Aspen Plus must be visible and maximized
- Do not move the mouse during execution
- Screen resolution should be standard (1920x1080 recommended)
"""
import win32com.client as win32
import time
import os

# Try to import UI automation libraries
try:
    import pyautogui
    import pywinauto
    from pywinauto import Application
    HAS_UI_AUTO = True
except ImportError:
    HAS_UI_AUTO = False
    print("UI automation libraries not available.")
    print("Install with: pip install pyautogui pywinauto")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
BKP_FILE = os.path.join(PROJECT_DIR, "MethanolPlant_streams.bkp")

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def connect_aspen():
    """Connect to Aspen Plus and load the simulation."""
    log("Connecting to Aspen Plus...")
    
    try:
        aspen = win32.GetActiveObject("Apwn.Document")
        log("  Connected to running instance")
    except:
        log("  Loading from file...")
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitFromArchive2(BKP_FILE)
        aspen.Visible = True
        aspen.SuppressDialogs = 0  # Allow dialogs for manual interaction
    
    return aspen

def check_flowsheet(aspen):
    """Check current flowsheet status."""
    streams = aspen.Tree.FindNode(r"\Data\Streams")
    blocks = aspen.Tree.FindNode(r"\Data\Blocks")
    
    s_count = streams.Elements.Count if streams else 0
    b_count = blocks.Elements.Count if blocks else 0
    
    log(f"Current state: {s_count} streams, {b_count} blocks")
    return s_count, b_count

def print_manual_instructions():
    """Print detailed manual instructions for adding blocks."""
    
    instructions = """
================================================================================
                    MANUAL BLOCK CREATION INSTRUCTIONS
================================================================================

Since programmatic block creation is not supported via COM, please add the 
following blocks manually in the Aspen Plus GUI:

FLOWSHEET STRUCTURE:
====================

Section 1: REFORMING
--------------------
1. MIX-FEED (Mixer)
   - Inputs: NG-FEED, STEAM, O2-FEED
   - Output: ATR-IN

2. B-ATR (RGibbs - Equilibrium Reactor)
   - Input: ATR-IN
   - Output: HOT-SYN
   - Settings: P = 30 bar, Check all possible products

3. B-COOL (Heater)
   - Input: HOT-SYN
   - Output: COLD-SYN
   - Settings: T = 40°C

4. B-FLASH (Flash2)
   - Input: COLD-SYN
   - Outputs: DRY-GAS (vapor), WATER-DR (liquid)

Section 2: COMPRESSION
----------------------
5. B-COMP (Compr - Compressor)
   - Input: DRY-GAS
   - Output: HP-GAS
   - Settings: P = 80 bar, Isentropic

Section 3: SYNTHESIS LOOP
-------------------------
6. MIX-LOOP (Mixer)
   - Inputs: HP-GAS, RECYCLE
   - Output: R-IN

7. B-SYN (RStoic - Stoichiometric Reactor)
   - Input: R-IN
   - Output: R-OUT
   - Settings: T = 250°C, P = 80 bar
   - Reaction: CO + 2H2 -> CH3OH (25% conversion)

8. B-SEP (Flash2)
   - Input: R-OUT
   - Outputs: GAS-PURG (vapor), CRUDE-ME (liquid)

9. SPLIT (FSplit)
   - Input: GAS-PURG
   - Outputs: PURGE (5%), RECYCLE (95%)

Section 4: PURIFICATION
-----------------------
10. B-DIST (Sep or RadFrac)
    - Input: CRUDE-ME
    - Outputs: MEOH-PRO, WASTE-H2O
    - Settings: 99.5% methanol recovery

================================================================================
                           STEP-BY-STEP GUIDE
================================================================================

1. In Aspen Plus, go to the SIMULATION tab (main flowsheet view)

2. Open the Model Palette (View > Model Palette if not visible)

3. For each block:
   a. Find the block type in the palette (Mixers/Splitters, Reactors, etc.)
   b. Click on the block type
   c. Click on the flowsheet canvas to place it
   d. Double-click to rename it to the name above
   e. Double-click again to open specifications
   f. Connect the streams as listed above

4. To connect streams:
   a. Click on the Material Streams tool in the palette
   b. Click on the stream source (block outlet or existing stream)
   c. Click on the stream destination (block inlet)

5. Save the file as MethanolPlant.bkp when complete

================================================================================
                           STREAM CONNECTIONS
================================================================================

Feed Streams (already created):
- NG-FEED -> MIX-FEED inlet
- STEAM -> MIX-FEED inlet  
- O2-FEED -> MIX-FEED inlet

Intermediate Streams (auto-created when connecting):
- ATR-IN: MIX-FEED -> B-ATR
- HOT-SYN: B-ATR -> B-COOL
- COLD-SYN: B-COOL -> B-FLASH
- DRY-GAS: B-FLASH vapor -> B-COMP
- WATER-DR: B-FLASH liquid (product)
- HP-GAS: B-COMP -> MIX-LOOP
- R-IN: MIX-LOOP -> B-SYN
- R-OUT: B-SYN -> B-SEP
- GAS-PURG: B-SEP vapor -> SPLIT
- CRUDE-ME: B-SEP liquid -> B-DIST
- PURGE: SPLIT -> (product)
- RECYCLE: SPLIT -> MIX-LOOP
- MEOH-PRO: B-DIST -> (product)
- WASTE-H2O: B-DIST -> (product)

================================================================================

After adding all blocks and connections:
1. Save the file (Ctrl+S)
2. Run this script again to verify: python check_flowsheet.py

================================================================================
"""
    print(instructions)

def main():
    log("=" * 60)
    log("METHANOL PLANT FLOWSHEET BUILDER")
    log("=" * 60)
    
    # Connect to Aspen Plus
    aspen = connect_aspen()
    time.sleep(3)
    
    # Check current state
    s_count, b_count = check_flowsheet(aspen)
    
    if b_count >= 10:
        log("\nFlowsheet appears complete!")
        log("All blocks are present.")
        return 0
    
    if b_count > 0:
        log(f"\nPartial flowsheet: {b_count} blocks exist")
    else:
        log("\nNo blocks found in flowsheet")
    
    # Print manual instructions
    print_manual_instructions()
    
    # Save current state
    save_path = os.path.join(PROJECT_DIR, "MethanolPlant_ready.bkp")
    try:
        aspen.SaveAs(save_path)
        log(f"\nSaved current state to: {save_path}")
    except:
        pass
    
    log("\nAspen Plus window should be visible.")
    log("Please follow the instructions above to add the blocks.")
    
    return 0

if __name__ == "__main__":
    exit(main())
