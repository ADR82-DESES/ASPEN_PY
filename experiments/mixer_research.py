"""
MIXER BLOCK RESEARCH - With File Logging
Tests different methods to add a Mixer block and logs everything
"""
import win32com.client as win32
import sys

# Open log file
log = open("mixer_research_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("MIXER BLOCK CREATION RESEARCH")
log_print("="*70)

# Connect and initialize
log_print("\n[1] Connecting and Initializing...")
try:
    aspen = win32.Dispatch("Apwn.Document")
    log_print("  Connected to Dispatch")
    
    aspen.InitNew()
    log_print("  [OK] InitNew() successful")
    
    aspen.Visible = True
    log_print("  [OK] Made visible")
    
except Exception as e:
    log_print(f"  [FAIL] {e}")
    log.close()
    sys.exit(1)

# Test adding a Mixer with different type names
log_print("\n[2] Testing Mixer Block Creation...")
log_print("-"*70)

# Common Aspen Plus block type names for mixers
mixer_types = [
    "Mixer",
    "MIXER", 
    "MIX",
    "Mix",
    "mixer",
    "",  # No type specified
]

for i, block_type in enumerate(mixer_types):
    log_print(f"\nTest {i+1}: Add('MIXER', '{block_type}')")
    
    try:
        blocks = aspen.Tree.FindNode(r"\Data\Blocks")
        
        if block_type == "":
            # Try with just one argument
            blocks.Elements.Add("MIXER")
            log_print(f"  [SUCCESS] Add('MIXER') worked!")
        else:
            blocks.Elements.Add("MIXER", block_type)
            log_print(f"  [SUCCESS] Add('MIXER', '{block_type}') worked!")
        
        # Verify it was created
        mixer = aspen.Tree.FindNode(r"\Data\Blocks\MIXER")
        if mixer:
            log_print("  [VERIFIED] MIXER block found in tree")
            
            # Try to get block type
            try:
                input_node = mixer.FindNode("Input")
                if input_node:
                    type_node = input_node.FindNode("TYPE")
                    if type_node and type_node.Value:
                        log_print(f"  Block TYPE value: {type_node.Value}")
            except Exception as e:
                log_print(f"  Could not read TYPE: {str(e)[:60]}")
            
            # This one worked! Save it
            log_print(f"\n*** SOLUTION FOUND: Use Add('MIXER', '{block_type}') ***\n")
            
            # Don't remove it, keep it for connection tests
            break
        else:
            log_print("  [WARNING] Block added but not found in tree")
            
    except Exception as e:
        error_str = str(e)
        if "Invalid Block/Model" in error_str:
            log_print(f"  [FAIL] Invalid block type '{block_type}'")
        else:
            log_print(f"  [FAIL] {error_str[:100]}")

# If we have a MIXER, try to connect streams
log_print("\n[3] Testing Stream Connections...")
log_print("-"*70)

mixer = aspen.Tree.FindNode(r"\Data\Blocks\MIXER")
if mixer:
    log_print("MIXER block exists, testing connections...")
    
    # First create streams
    log_print("\nCreating test streams...")
    try:
        streams = aspen.Tree.FindNode(r"\Data\Streams")
        for stream in ["WATER1", "WATER2", "OUT"]:
            try:
                streams.Elements.Add(stream)
                log_print(f"  [OK] Created {stream}")
            except:
                log_print(f"  [INFO] {stream} already exists")
    except Exception as e:
        log_print(f"  [ERROR] {e}")
    
    # Try different connection paths
    log_print("\nTesting inlet connection paths...")
    
    inlet_paths = [
        r"Input\FEED",
        r"Ports\F(IN)",
        r"Ports\F",
        r"Connections\Inlet",
        r"Input\F",
    ]
    
    for path in inlet_paths:
        log_print(f"\nTrying: \\Data\\Blocks\\MIXER\\{path}")
        try:
            full_path = rf"\Data\Blocks\MIXER\{path}"
            node = aspen.Tree.FindNode(full_path)
            
            if node:
                log_print(f"  [OK] Node exists")
                
                # Try to add streams
                try:
                    node.Elements.Add("WATER1")
                    log_print(f"  [SUCCESS] Added WATER1")
                    
                    node.Elements.Add("WATER2")
                    log_print(f"  [SUCCESS] Added WATER2")
                    
                    log_print(f"\n*** INLET CONNECTION WORKS: {path} ***\n")
                    break
                    
                except Exception as e:
                    log_print(f"  [FAIL] Cannot add streams: {str(e)[:80]}")
            else:
                log_print(f"  [FAIL] Node not found")
                
        except Exception as e:
            log_print(f"  [ERROR] {str(e)[:80]}")
    
    # Try outlet paths
    log_print("\nTesting outlet connection paths...")
    
    outlet_paths = [
        r"Output\PROD",
        r"Ports\P(OUT)",
        r"Ports\P",
        r"Connections\Outlet",
        r"Output\P",
    ]
    
    for path in outlet_paths:
        log_print(f"\nTrying: \\Data\\Blocks\\MIXER\\{path}")
        try:
            full_path = rf"\Data\Blocks\MIXER\{path}"
            node = aspen.Tree.FindNode(full_path)
            
            if node:
                log_print(f"  [OK] Node exists")
                
                # Try to add stream
                try:
                    node.Elements.Add("OUT")
                    log_print(f"  [SUCCESS] Added OUT")
                    log_print(f"\n*** OUTLET CONNECTION WORKS: {path} ***\n")
                    break
                    
                except Exception as e:
                    log_print(f"  [FAIL] Cannot add stream: {str(e)[:80]}")
            else:
                log_print(f"  [FAIL] Node not found")
                
        except Exception as e:
            log_print(f"  [ERROR] {str(e)[:80]}")

else:
    log_print("[SKIP] No MIXER block to test connections")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log_print("\nResults saved to mixer_research_log.txt")
log_print("Check Aspen Plus window to see what was created")

log.close()
print("\n✓ Research complete! Check mixer_research_log.txt for results.")
