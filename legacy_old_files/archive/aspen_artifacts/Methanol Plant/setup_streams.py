"""
Methanol Plant - Stream Setup Script
=====================================
This script creates all the feed streams via COM.
After running this, you'll need to add the blocks manually in the Aspen Plus GUI.

Design Basis:
- 10,000 TPD Methanol Production
- ATR (Autothermal Reforming) Technology
"""
import win32com.client as win32
import os
import time

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
BKP_FILE = os.path.join(PROJECT_DIR, "MethanolPlant_streams.bkp")

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def main():
    log("=" * 60)
    log("METHANOL PLANT - STREAM SETUP")
    log("=" * 60)
    
    # Connect or create
    log("\n[1] Connecting to Aspen Plus...")
    try:
        aspen = win32.GetActiveObject("Apwn.Document")
        log("    Connected to running instance")
    except:
        log("    Creating new simulation...")
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitNew()
        aspen.Visible = True
    
    time.sleep(3)
    
    # Define all streams for the methanol plant
    streams_data = {
        # Feed Streams
        "NG-FEED": {"temp": 40, "pres": 30, "flow": 220000, "desc": "Natural Gas Feed (100% CH4)"},
        "STEAM": {"temp": 250, "pres": 35, "flow": 148500, "desc": "Process Steam"},
        "O2-FEED": {"temp": 150, "pres": 30, "flow": 264000, "desc": "Oxygen Feed"},
        
        # Intermediate Streams (will be connected to blocks)
        "ATR-IN": {"desc": "ATR Reactor Inlet (mixed feed)"},
        "HOT-SYN": {"desc": "Hot Syngas from ATR"},
        "COLD-SYN": {"desc": "Cooled Syngas"},
        "DRY-GAS": {"desc": "Dry Syngas (after water knockout)"},
        "WATER-DR": {"desc": "Condensed Water from Flash"},
        "HP-GAS": {"desc": "High Pressure Syngas"},
        "R-IN": {"desc": "Synthesis Reactor Inlet"},
        "R-OUT": {"desc": "Synthesis Reactor Outlet"},
        "GAS-PURG": {"desc": "Gas to Purge Splitter"},
        "CRUDE-ME": {"desc": "Crude Methanol"},
        "PURGE": {"desc": "Purge Gas"},
        "RECYCLE": {"desc": "Recycle Gas"},
        "MEOH-PRO": {"desc": "Methanol Product"},
        "WASTE-H2O": {"desc": "Waste Water"},
    }
    
    log("\n[2] Creating streams...")
    
    streams_node = aspen.Tree.FindNode(r"\Data\Streams")
    created = 0
    
    for stream_name, data in streams_data.items():
        try:
            # Check if exists
            existing = aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}")
            if existing:
                log(f"    [EXISTS] {stream_name}")
                continue
            
            # Create stream
            streams_node.Elements.Add(stream_name)
            created += 1
            log(f"    [CREATED] {stream_name} - {data.get('desc', '')}")
            
        except Exception as e:
            log(f"    [ERROR] {stream_name}: {e}")
    
    log(f"\n    Created {created} new streams")
    
    # Count total
    total_streams = streams_node.Elements.Count
    log(f"    Total streams: {total_streams}")
    
    # Save
    log(f"\n[3] Saving to: {BKP_FILE}")
    try:
        aspen.SaveAs(BKP_FILE)
        log("    Saved successfully!")
    except Exception as e:
        log(f"    Save error: {e}")
    
    # Print next steps
    log("\n" + "=" * 60)
    log("NEXT STEPS - ADD BLOCKS MANUALLY IN ASPEN PLUS GUI")
    log("=" * 60)
    
    blocks_info = [
        ("MIX-FEED", "Mixer", "Combines NG-FEED + STEAM + O2-FEED -> ATR-IN"),
        ("B-ATR", "RGibbs", "ATR Reactor: ATR-IN -> HOT-SYN (T=1000C, P=30bar)"),
        ("B-COOL", "Heater", "Syngas Cooler: HOT-SYN -> COLD-SYN (T=40C)"),
        ("B-FLASH", "Flash2", "Water Knockout: COLD-SYN -> DRY-GAS + WATER-DR"),
        ("B-COMP", "Compr", "Compressor: DRY-GAS -> HP-GAS (P=80bar)"),
        ("MIX-LOOP", "Mixer", "Recycle Mixer: HP-GAS + RECYCLE -> R-IN"),
        ("B-SYN", "RStoic/REquil", "Synthesis: R-IN -> R-OUT (T=250C, P=80bar)"),
        ("B-SEP", "Flash2", "HP Separator: R-OUT -> GAS-PURG + CRUDE-ME"),
        ("SPLIT", "FSplit", "Purge Split: GAS-PURG -> PURGE (5%) + RECYCLE (95%)"),
        ("B-DIST", "Sep/RadFrac", "Distillation: CRUDE-ME -> MEOH-PRO + WASTE-H2O"),
    ]
    
    log("\nBlocks to add (in order):")
    log("-" * 60)
    for i, (name, btype, desc) in enumerate(blocks_info, 1):
        log(f"{i:2}. {name:12} ({btype:8}) - {desc}")
    
    log("\n" + "=" * 60)
    log("HOW TO ADD BLOCKS IN ASPEN PLUS:")
    log("=" * 60)
    log("1. Go to the Model Palette (usually on the left)")
    log("2. Drag block type (e.g., Mixer) onto the flowsheet")
    log("3. Name it according to the list above")
    log("4. Connect streams to block inlets/outlets")
    log("5. Set block parameters (T, P, etc.)")
    log("6. Save the file")
    log("=" * 60)
    
    return 0

if __name__ == "__main__":
    exit(main())
