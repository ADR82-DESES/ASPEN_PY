"""
DEEP RESEARCH: Find Available Block Types in Aspen Plus
This script explores the Aspen Plus object model to find valid block types
"""
import win32com.client as win32
import sys

log = open("block_types_research.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS BLOCK TYPES RESEARCH")
log_print("="*70)

# Connect and initialize
log_print("\n[1] Initializing...")
try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    aspen.Visible = True
    log_print("[OK] Initialized")
except Exception as e:
    log_print(f"[FAIL] {e}")
    log.close()
    sys.exit(1)

# Strategy 1: Try to access model library or block type information
log_print("\n[2] Exploring Aspen Plus Object Model...")
log_print("-"*70)

# Check for Application object
log_print("\nChecking for Application object...")
try:
    if hasattr(aspen, 'Application'):
        app = aspen.Application
        log_print(f"  [OK] Application: {app}")
        
        # Check for ModelLibrary or similar
        if hasattr(app, 'ModelLibrary'):
            log_print("  [OK] Has ModelLibrary")
        if hasattr(app, 'Models'):
            log_print("  [OK] Has Models")
        if hasattr(app, 'BlockTypes'):
            log_print("  [OK] Has BlockTypes")
except Exception as e:
    log_print(f"  [INFO] {e}")

# Strategy 2: Check if there's a Models or Templates node in the tree
log_print("\n[3] Searching for Model/Template Information in Tree...")
log_print("-"*70)

search_paths = [
    r"\Data\Models",
    r"\Data\BlockTypes",
    r"\Models",
    r"\Templates",
    r"\Data\Flowsheeting Options\Design-Spec",
]

for path in search_paths:
    try:
        node = aspen.Tree.FindNode(path)
        if node:
            log_print(f"  [FOUND] {path}")
            
            # Try to enumerate
            if hasattr(node, 'Elements'):
                try:
                    count = node.Elements.Count
                    log_print(f"    Has {count} elements")
                    
                    for i in range(min(count, 10)):
                        try:
                            elem = node.Elements.Item(i)
                            log_print(f"      - {elem.Name}")
                        except:
                            pass
                except:
                    pass
        else:
            log_print(f"  [NOT FOUND] {path}")
    except Exception as e:
        log_print(f"  [ERROR] {path}: {str(e)[:60]}")

# Strategy 3: Try known Aspen Plus block types from documentation
log_print("\n[4] Testing Known Aspen Plus Block Types...")
log_print("-"*70)

# Common Aspen Plus block type IDs (from documentation)
known_types = [
    ("Heater", "HEATER"),
    ("Cooler", "HEATER"),  # Heater can be cooler too
    ("Pump", "PUMP"),
    ("Valve", "VALVE"),
    ("Flash2", "FLASH2"),
    ("Flash3", "FLASH3"),
    ("Mixer", "MIXER"),  # Try again
    ("FSplit", "FSPLIT"),
    ("Sep", "SEP"),
    ("Sep2", "SEP2"),
    ("Compr", "COMPR"),
    ("MCompr", "MCOMPR"),
    ("Turbine", "COMPR"),
    ("HeatX", "HEATX"),
    ("RadFrac", "RADFRAC"),
    ("Extract", "EXTRACT"),
    ("Decanter", "DECANTER"),
    ("RPlug", "RPLUG"),
    ("RCSTR", "RCSTR"),
    ("RYield", "RYIELD"),
    ("RStoic", "RSTOIC"),
    ("RGibbs", "RGIBBS"),
    ("REquil", "REQUIL"),
]

successful_types = []

for block_name, block_type in known_types:
    log_print(f"\nTesting: Add('TEST_{block_name}', '{block_type}')")
    try:
        aspen.Tree.FindNode(r"\Data\Blocks").Elements.Add(f"TEST_{block_name}", block_type)
        log_print(f"  [SUCCESS] '{block_type}' is valid!")
        successful_types.append((block_name, block_type))
        
        # Clean up
        try:
            aspen.Tree.FindNode(r"\Data\Blocks").Elements.Remove(f"TEST_{block_name}")
        except:
            pass
            
    except Exception as e:
        if "Invalid" in str(e):
            log_print(f"  [FAIL] Invalid type")
        else:
            log_print(f"  [FAIL] {str(e)[:60]}")

# Strategy 4: If HEATER works, use it as a workaround
log_print("\n[5] Testing Workaround: Can we change block type after creation?")
log_print("-"*70)

if successful_types:
    log_print(f"\nFound {len(successful_types)} working block types:")
    for name, type_id in successful_types:
        log_print(f"  - {name}: {type_id}")
    
    # Try to create a HEATER and see if we can change its type
    log_print("\nTesting if we can modify block type after creation...")
    try:
        aspen.Tree.FindNode(r"\Data\Blocks").Elements.Add("TESTBLOCK", "HEATER")
        log_print("  [OK] Created HEATER")
        
        # Try to find and modify TYPE
        block = aspen.Tree.FindNode(r"\Data\Blocks\TESTBLOCK")
        if block:
            input_node = block.FindNode("Input")
            if input_node:
                type_node = input_node.FindNode("TYPE")
                if type_node:
                    log_print(f"  Current TYPE: {type_node.Value}")
                    
                    # Try to change it
                    try:
                        type_node.Value = "MIXER"
                        log_print("  [SUCCESS] Changed TYPE to MIXER!")
                        log_print("\n*** WORKAROUND FOUND: Create as HEATER, change TYPE to MIXER ***")
                    except Exception as e:
                        log_print(f"  [FAIL] Cannot change TYPE: {e}")
        
        # Clean up
        aspen.Tree.FindNode(r"\Data\Blocks").Elements.Remove("TESTBLOCK")
        
    except Exception as e:
        log_print(f"  [ERROR] {e}")

# Strategy 5: Check Aspen Plus version-specific block types
log_print("\n[6] Checking for Aspen Plus V40 Specific Block Types...")
log_print("-"*70)

v40_types = [
    ("Mixer", "Mix"),
    ("Mixer", "MIXR"),
    ("Mixer", "MX"),
    ("Mixer", "M"),
]

for block_name, block_type in v40_types:
    log_print(f"\nTesting: Add('MIXER', '{block_type}')")
    try:
        aspen.Tree.FindNode(r"\Data\Blocks").Elements.Add("MIXER", block_type)
        log_print(f"  [SUCCESS] '{block_type}' works!")
        log_print(f"\n*** SOLUTION: Use Add('MIXER', '{block_type}') ***")
        
        # Don't clean up - keep it for inspection
        break
        
    except Exception as e:
        log_print(f"  [FAIL] {str(e)[:80]}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)

if successful_types:
    log_print(f"\nFound {len(successful_types)} valid block types")
    log_print("Check block_types_research.txt for full details")
else:
    log_print("\nNo valid block types found through standard methods")
    log_print("This suggests blocks may need to be added differently")

log.close()
print("\n✓ Research complete! Check block_types_research.txt")
