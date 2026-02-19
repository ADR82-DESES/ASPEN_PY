"""
Build Methanol Plant Flowsheet via COM
=======================================
Creates the complete flowsheet structure programmatically based on DESIGN_BASIS.md
"""
import win32com.client as win32
import os
import time

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
BKP_FILE = os.path.join(PROJECT_DIR, "MethanolPlant.bkp")

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def main():
    log("=" * 60)
    log("BUILDING METHANOL PLANT FLOWSHEET")
    log("=" * 60)
    
    # Connect to running instance or load file
    log("\n[1] Connecting to Aspen Plus...")
    
    aspen = None
    try:
        aspen = win32.GetActiveObject("Apwn.Document")
        log("    Connected to running instance")
    except:
        log("    Loading from file...")
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitFromArchive2(BKP_FILE)
        aspen.Visible = True
        log("    File loaded")
    
    time.sleep(3)
    
    # Check if flowsheet already exists
    log("\n[2] Checking current flowsheet status...")
    streams_node = aspen.Tree.FindNode(r"\Data\Streams")
    blocks_node = aspen.Tree.FindNode(r"\Data\Blocks")
    
    has_streams = streams_node and streams_node.Elements.Count > 0
    has_blocks = blocks_node and blocks_node.Elements.Count > 0
    
    if has_streams and has_blocks:
        log("    Flowsheet already exists!")
        log(f"    Streams: {streams_node.Elements.Count}")
        log(f"    Blocks: {blocks_node.Elements.Count}")
        return 0
    
    log("    Flowsheet is empty - building now...")
    
    # Build flowsheet using Application methods
    log("\n[3] Building Flowsheet...")
    
    try:
        # Access the flowsheet
        app = aspen.Application
        
        # Define streams
        log("    Creating streams...")
        streams_def = [
            ("NG-FEED", {"TEMP": 40, "PRES": 30, "MASSFLOW": 220000, "CH4": 1.0}),
            ("STEAM", {"TEMP": 250, "PRES": 35, "MASSFLOW": 148500, "H2O": 1.0}),
            ("O2-FEED", {"TEMP": 150, "PRES": 30, "MASSFLOW": 264000, "O2": 1.0}),
        ]
        
        for stream_name, props in streams_def:
            try:
                # Create stream via tree
                stream_path = rf"\Data\Streams\{stream_name}"
                node = aspen.Tree.FindNode(stream_path)
                if not node:
                    # Create new stream
                    aspen.Tree.FindNode(r"\Data\Streams").Elements.Add(stream_name)
                    log(f"      Created: {stream_name}")
                else:
                    log(f"      Exists: {stream_name}")
            except Exception as e:
                log(f"      Error creating {stream_name}: {e}")
        
        # Define blocks with their types
        log("\n    Creating blocks...")
        blocks_def = [
            ("MIX-FEED", "Mixer"),
            ("B-ATR", "RGibbs"),
            ("B-COOL", "Heater"),
            ("B-FLASH", "Flash2"),
            ("B-COMP", "Compr"),
            ("MIX-LOOP", "Mixer"),
            ("B-SYN", "REquil"),
            ("B-SEP", "Flash2"),
            ("SPLIT", "FSplit"),
            ("B-DIST", "Sep"),
        ]
        
        for block_name, block_type in blocks_def:
            try:
                block_path = rf"\Data\Blocks\{block_name}"
                node = aspen.Tree.FindNode(block_path)
                if not node:
                    # Create new block
                    aspen.Tree.FindNode(r"\Data\Blocks").Elements.Add(block_name)
                    
                    # Set block type
                    type_node = aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}\Input\TYPE")
                    if type_node:
                        type_node.Value = block_type
                    
                    log(f"      Created: {block_name} ({block_type})")
                else:
                    log(f"      Exists: {block_name}")
            except Exception as e:
                log(f"      Error creating {block_name}: {e}")
        
        log("\n[4] Saving simulation...")
        aspen.Save()
        log("    Saved!")
        
        # Verify
        log("\n[5] Verification...")
        streams_node = aspen.Tree.FindNode(r"\Data\Streams")
        blocks_node = aspen.Tree.FindNode(r"\Data\Blocks")
        
        stream_count = streams_node.Elements.Count if streams_node else 0
        block_count = blocks_node.Elements.Count if blocks_node else 0
        
        log(f"    Streams: {stream_count}")
        log(f"    Blocks: {block_count}")
        
        if stream_count > 0 or block_count > 0:
            log("\n[OK] Flowsheet building initiated!")
            log("     Complete the connectivity in Aspen Plus GUI.")
        else:
            log("\n[!] Could not create elements programmatically.")
            log("    Please use File > Import in Aspen Plus to load MethanolPlant.inp")
        
    except Exception as e:
        log(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    log("\n" + "=" * 60)
    log("DONE")
    log("=" * 60)
    return 0

if __name__ == "__main__":
    exit(main())
