"""
RESEARCH SCRIPT: Find the correct way to add a Mixer block
This script will try different approaches to add a Mixer block programmatically
"""
import win32com.client as win32
import sys

print("="*70)
print("MIXER BLOCK CREATION RESEARCH")
print("="*70)

# Connect and initialize
print("\n[1] Connecting and Initializing...")
try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    aspen.Visible = True
    print("[OK] Initialized")
except Exception as e:
    print(f"[FAIL] {e}")
    sys.exit(1)

# First, let's see what block types are available
print("\n[2] Exploring Block Types...")
try:
    blocks_node = aspen.Tree.FindNode(r"\Data\Blocks")
    
    # Try to see if there's a way to list available block types
    print("Checking for available methods on Blocks node...")
    
    # Check if there's a Types or Models collection
    if hasattr(blocks_node, 'Types'):
        print("  Has Types attribute")
        try:
            types = blocks_node.Types
            print(f"  Types: {types}")
        except Exception as e:
            print(f"  Cannot access Types: {e}")
    
    if hasattr(blocks_node, 'Models'):
        print("  Has Models attribute")
        try:
            models = blocks_node.Models
            print(f"  Models: {models}")
        except Exception as e:
            print(f"  Cannot access Models: {e}")
            
except Exception as e:
    print(f"[ERROR] {e}")

# Try different approaches to add a Mixer
print("\n[3] Testing Different Mixer Creation Methods...")

approaches = [
    {
        "name": "Approach 1: Add('MIXER', 'Mixer')",
        "func": lambda: aspen.Tree.FindNode(r"\Data\Blocks").Elements.Add("MIXER", "Mixer")
    },
    {
        "name": "Approach 2: Add('MIXER', 'MIXER')",
        "func": lambda: aspen.Tree.FindNode(r"\Data\Blocks").Elements.Add("MIXER", "MIXER")
    },
    {
        "name": "Approach 3: Add('MIXER', 'MIX')",
        "func": lambda: aspen.Tree.FindNode(r"\Data\Blocks").Elements.Add("MIXER", "MIX")
    },
    {
        "name": "Approach 4: Add('MIXER') only",
        "func": lambda: aspen.Tree.FindNode(r"\Data\Blocks").Elements.Add("MIXER")
    },
    {
        "name": "Approach 5: Add('MIXER', 'HEATER')",  # Try a different block type
        "func": lambda: aspen.Tree.FindNode(r"\Data\Blocks").Elements.Add("MIXER", "HEATER")
    },
]

successful_approach = None

for i, approach in enumerate(approaches):
    print(f"\n{i+1}. {approach['name']}")
    try:
        approach['func']()
        print("   [SUCCESS!] This approach worked!")
        successful_approach = approach['name']
        
        # Check if block was created
        mixer = aspen.Tree.FindNode(r"\Data\Blocks\MIXER")
        if mixer:
            print("   [VERIFIED] MIXER block exists in tree")
            
            # Try to see what type it is
            try:
                if hasattr(mixer, 'Input'):
                    input_node = mixer.FindNode("Input")
                    if input_node:
                        type_node = input_node.FindNode("TYPE")
                        if type_node:
                            print(f"   Block TYPE: {type_node.Value}")
            except:
                pass
        
        # Clean up for next test
        try:
            aspen.Tree.FindNode(r"\Data\Blocks").Elements.Remove("MIXER")
            print("   [CLEANUP] Removed for next test")
        except:
            pass
            
        break  # Stop if we found a working approach
        
    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 100:
            error_msg = error_msg[:100] + "..."
        print(f"   [FAILED] {error_msg}")

# If we found a working approach, try to create a complete flowsheet
if successful_approach:
    print(f"\n[4] Creating Complete Flowsheet with {successful_approach}")
    print("-"*70)
    
    try:
        # Add component
        print("Adding WATER component...")
        aspen.Tree.FindNode(r"\Data\Components\Specifications\Input\CAG_IDS").Elements.Add("WATER")
        print("  [OK]")
        
        # Set property method
        print("Setting property method...")
        aspen.Tree.FindNode(r"\Data\Properties\Global\Input\METHOD").Value = "IDEAL"
        print("  [OK]")
        
        # Create streams
        print("Creating streams...")
        streams = aspen.Tree.FindNode(r"\Data\Streams")
        for stream in ["WATER1", "WATER2", "OUT"]:
            streams.Elements.Add(stream)
            print(f"  [OK] {stream}")
        
        # Create mixer using successful approach
        print("Creating MIXER block...")
        approaches_dict = {a['name']: a['func'] for a in approaches}
        approaches_dict[successful_approach]()
        print("  [OK] MIXER")
        
        # Now try to connect streams
        print("Connecting streams...")
        
        # Try different connection paths
        connection_paths = [
            (r"\Data\Blocks\MIXER\Input\FEED", ["WATER1", "WATER2"]),
            (r"\Data\Blocks\MIXER\Ports\F(IN)", ["WATER1", "WATER2"]),
            (r"\Data\Blocks\MIXER\Connections\Inlet", ["WATER1", "WATER2"]),
        ]
        
        connected = False
        for inlet_path, inlet_streams in connection_paths:
            try:
                inlet_node = aspen.Tree.FindNode(inlet_path)
                if inlet_node:
                    for stream in inlet_streams:
                        inlet_node.Elements.Add(stream)
                    print(f"  [OK] Connected inlets via {inlet_path}")
                    connected = True
                    break
            except Exception as e:
                print(f"  [FAIL] {inlet_path}: {str(e)[:50]}")
        
        if connected:
            # Try outlet
            outlet_paths = [
                r"\Data\Blocks\MIXER\Output\PROD",
                r"\Data\Blocks\MIXER\Ports\P(OUT)",
                r"\Data\Blocks\MIXER\Connections\Outlet",
            ]
            
            for outlet_path in outlet_paths:
                try:
                    outlet_node = aspen.Tree.FindNode(outlet_path)
                    if outlet_node:
                        outlet_node.Elements.Add("OUT")
                        print(f"  [OK] Connected outlet via {outlet_path}")
                        break
                except Exception as e:
                    print(f"  [FAIL] {outlet_path}: {str(e)[:50]}")
        
        print("\n[SUCCESS] Flowsheet created programmatically!")
        print("Check Aspen Plus window to verify.")
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
else:
    print("\n[FAILED] Could not find a working approach to add Mixer block")
    print("\nLet me try to explore what block types ARE available...")
    
    # Try to add a simple heater to see if that works
    print("\nTrying to add a HEATER block as a test...")
    try:
        aspen.Tree.FindNode(r"\Data\Blocks").Elements.Add("TEST", "HEATER")
        print("[OK] HEATER block can be added!")
        print("This means the syntax is correct, but 'Mixer' might not be the right type name")
        
        # Clean up
        aspen.Tree.FindNode(r"\Data\Blocks").Elements.Remove("TEST")
    except Exception as e:
        print(f"[FAIL] {e}")

print("\n" + "="*70)
print("RESEARCH COMPLETE")
print("="*70)
print("\nCheck the output above to see which approach worked.")
print("If successful, we can update the automation scripts accordingly.")
