"""
Build Methanol Plant Flowsheet via Aspen Plus COM
==================================================
This script builds the complete flowsheet by creating streams and blocks
programmatically through the Aspen Plus COM interface.

Based on DESIGN_BASIS.md:
- 10,000 TPD Methanol Production
- ATR (Autothermal Reforming) Technology
"""
import win32com.client as win32
import os
import time

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
BKP_FILE = os.path.join(PROJECT_DIR, "MethanolPlant.bkp")

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def connect_aspen():
    """Connect to running Aspen Plus or create new instance."""
    log("Connecting to Aspen Plus...")
    
    # Try to connect to running instance
    try:
        aspen = win32.GetActiveObject("Apwn.Document")
        log("  Connected to running instance")
        return aspen
    except:
        pass
    
    # Create new instance
    log("  Creating new Aspen Plus instance...")
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    aspen.Visible = True
    log("  New simulation created")
    
    return aspen

def setup_components(aspen):
    """Define the components for the simulation."""
    log("\nSetting up components...")
    
    components = [
        ("CH4", "METHANE"),
        ("H2O", "WATER"),
        ("O2", "OXYGEN"),
        ("CO", "CARBON-MONOXIDE"),
        ("CO2", "CARBON-DIOXIDE"),
        ("H2", "HYDROGEN"),
        ("CH3OH", "METHANOL"),
        ("N2", "NITROGEN"),
    ]
    
    comp_node = aspen.Tree.FindNode(r"\Data\Components\Specifications")
    if not comp_node:
        log("  ERROR: Cannot access Components node")
        return False
    
    # Check if components already exist
    try:
        existing = comp_node.Elements.Count
        if existing >= len(components):
            log(f"  Components already defined ({existing} found)")
            return True
    except:
        pass
    
    log(f"  Adding {len(components)} components...")
    for comp_id, comp_name in components:
        try:
            # Add component
            comp_node.Elements.Add(comp_id)
            log(f"    Added: {comp_id}")
        except Exception as e:
            log(f"    {comp_id}: {e}")
    
    return True

def create_streams(aspen):
    """Create the feed streams."""
    log("\nCreating streams...")
    
    streams_node = aspen.Tree.FindNode(r"\Data\Streams")
    if not streams_node:
        log("  ERROR: Cannot access Streams node")
        return False
    
    # Define feed streams
    feeds = [
        ("NG-FEED", {"temp": 40, "pres": 30, "flow": 220000, "comp": "CH4"}),
        ("STEAM", {"temp": 250, "pres": 35, "flow": 148500, "comp": "H2O"}),
        ("O2-FEED", {"temp": 150, "pres": 30, "flow": 264000, "comp": "O2"}),
    ]
    
    for stream_name, props in feeds:
        try:
            # Check if exists
            existing = aspen.Tree.FindNode(rf"\Data\Streams\{stream_name}")
            if existing:
                log(f"  {stream_name}: Already exists")
                continue
            
            # Add stream
            streams_node.Elements.Add(stream_name)
            log(f"  Created: {stream_name}")
            
            # Set properties
            try:
                # Temperature
                temp_path = rf"\Data\Streams\{stream_name}\Input\TEMP\MIXED"
                temp_node = aspen.Tree.FindNode(temp_path)
                if temp_node:
                    temp_node.Value = props["temp"]
                
                # Pressure
                pres_path = rf"\Data\Streams\{stream_name}\Input\PRES\MIXED"
                pres_node = aspen.Tree.FindNode(pres_path)
                if pres_node:
                    pres_node.Value = props["pres"]
                
                # Flow
                flow_path = rf"\Data\Streams\{stream_name}\Input\TOTFLOW\MIXED"
                flow_node = aspen.Tree.FindNode(flow_path)
                if flow_node:
                    flow_node.Value = props["flow"]
                
                log(f"    Set: T={props['temp']}C, P={props['pres']}bar, F={props['flow']}kg/hr")
            except Exception as e:
                log(f"    Warning setting properties: {e}")
                
        except Exception as e:
            log(f"  ERROR creating {stream_name}: {e}")
    
    return True

def create_blocks(aspen):
    """Create the process blocks."""
    log("\nCreating blocks...")
    
    blocks_node = aspen.Tree.FindNode(r"\Data\Blocks")
    if not blocks_node:
        log("  ERROR: Cannot access Blocks node")
        return False
    
    # Define blocks: (name, type, description)
    blocks = [
        ("MIX-FEED", "Mixer", "Feed Mixer"),
        ("ATR", "RGibbs", "ATR Reactor"),
        ("COOL1", "Heater", "Syngas Cooler"),
        ("FLASH1", "Flash2", "Water Knockout"),
        ("COMP1", "Compr", "Syngas Compressor"),
        ("MIX-LOOP", "Mixer", "Recycle Mixer"),
        ("REACTOR", "RStoic", "Methanol Synthesis"),
        ("SEP1", "Flash2", "HP Separator"),
        ("SPLIT1", "FSplit", "Purge Splitter"),
        ("DIST1", "Sep", "Methanol Purification"),
    ]
    
    created = 0
    for block_name, block_type, desc in blocks:
        try:
            # Check if exists
            existing = aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}")
            if existing:
                log(f"  {block_name}: Already exists")
                continue
            
            # Add block - need to specify the model type
            # The format depends on Aspen version
            try:
                blocks_node.Elements.Add(block_name)
                log(f"  Created: {block_name} ({desc})")
                created += 1
            except Exception as e:
                log(f"  Cannot create {block_name}: {e}")
                
        except Exception as e:
            log(f"  ERROR with {block_name}: {e}")
    
    log(f"  Created {created} blocks")
    return created > 0

def verify_flowsheet(aspen):
    """Verify the flowsheet structure."""
    log("\nVerifying flowsheet...")
    
    # Count streams
    streams_node = aspen.Tree.FindNode(r"\Data\Streams")
    stream_count = 0
    stream_names = []
    if streams_node:
        try:
            stream_count = streams_node.Elements.Count
            for i in range(stream_count):
                stream_names.append(streams_node.Elements.Item(i).Name)
        except:
            pass
    
    # Count blocks
    blocks_node = aspen.Tree.FindNode(r"\Data\Blocks")
    block_count = 0
    block_names = []
    if blocks_node:
        try:
            block_count = blocks_node.Elements.Count
            for i in range(block_count):
                block_names.append(blocks_node.Elements.Item(i).Name)
        except:
            pass
    
    log(f"  Streams: {stream_count}")
    for s in stream_names:
        log(f"    - {s}")
    
    log(f"  Blocks: {block_count}")
    for b in block_names:
        log(f"    - {b}")
    
    return stream_count, block_count

def save_simulation(aspen, filepath):
    """Save the simulation."""
    log(f"\nSaving to: {filepath}")
    try:
        aspen.SaveAs(filepath)
        log("  Saved successfully!")
        return True
    except Exception as e:
        log(f"  ERROR: {e}")
        return False

def main():
    log("=" * 60)
    log("METHANOL PLANT FLOWSHEET BUILDER (COM)")
    log("=" * 60)
    
    # Connect
    aspen = connect_aspen()
    if not aspen:
        return 1
    
    time.sleep(3)
    
    # Setup components
    setup_components(aspen)
    
    # Create streams
    create_streams(aspen)
    
    # Create blocks
    create_blocks(aspen)
    
    # Verify
    streams, blocks = verify_flowsheet(aspen)
    
    # Save
    save_simulation(aspen, BKP_FILE)
    
    log("\n" + "=" * 60)
    log("SUMMARY")
    log("=" * 60)
    log(f"  Streams: {streams}")
    log(f"  Blocks: {blocks}")
    
    if streams > 0:
        log("\n  Next steps:")
        log("  1. Open MethanolPlant.bkp in Aspen Plus")
        log("  2. Complete block specifications in the GUI")
        log("  3. Connect streams to blocks using the flowsheet")
        log("  4. Run the simulation")
    
    log("\nDone!")
    return 0

if __name__ == "__main__":
    exit(main())
