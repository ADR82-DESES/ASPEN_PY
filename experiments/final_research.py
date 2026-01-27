"""
FINAL RESEARCH: Tree Initialization and Template Approach
Try to properly initialize the tree structure before adding blocks
"""
import win32com.client as win32
import sys
import time

log = open("final_research_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("FINAL RESEARCH: PROPER TREE INITIALIZATION")
log_print("="*70)

# Connect
log_print("\n[1] Connecting...")
try:
    aspen = win32.Dispatch("Apwn.Document")
    log_print("[OK] Connected")
except Exception as e:
    log_print(f"[FAIL] {e}")
    log.close()
    sys.exit(1)

# Try InitFromTemplate2 with a simple template
log_print("\n[2] Trying InitFromTemplate2...")
log_print("-"*70)

template_attempts = [
    "MIXERSET.apw",
    "BLANK.apw",
    "General.apw",
    "",  # Empty string
]

template_worked = False

for template in template_attempts:
    if template:
        log_print(f"\nTrying template: '{template}'")
    else:
        log_print(f"\nTrying InitNew() instead...")
        
    try:
        if template:
            aspen.InitFromTemplate2(template)
        else:
            aspen.InitNew()
            
        log_print("  [OK] Initialization successful")
        aspen.Visible = True
        
        # Wait a moment for tree to populate
        time.sleep(2)
        
        # Check if Components node exists now
        comp_node = aspen.Tree.FindNode(r"\Data\Components\Specifications\Input\CAG_IDS")
        if comp_node:
            log_print("  [OK] Components node exists!")
            template_worked = True
            
            # Check Blocks node
            blocks_node = aspen.Tree.FindNode(r"\Data\Blocks")
            if blocks_node:
                log_print("  [OK] Blocks node exists!")
                
                # Try to see if there are any blocks already
                try:
                    count = blocks_node.Elements.Count
                    log_print(f"  [INFO] Blocks node has {count} elements")
                    
                    if count > 0:
                        log_print("  [INFO] Template includes pre-existing blocks:")
                        for i in range(min(count, 5)):
                            try:
                                block = blocks_node.Elements.Item(i)
                                log_print(f"    - {block.Name}")
                                
                                # Check the type of this block
                                try:
                                    input_node = block.FindNode("Input")
                                    if input_node:
                                        type_node = input_node.FindNode("TYPE")
                                        if type_node:
                                            log_print(f"      TYPE: {type_node.Value}")
                                except:
                                    pass
                            except:
                                pass
                except:
                    pass
            
            break
        else:
            log_print("  [WARN] Components node still doesn't exist")
            
    except Exception as e:
        log_print(f"  [FAIL] {str(e)[:100]}")

if not template_worked:
    log_print("\n[ERROR] Could not properly initialize tree structure")
    log_print("This suggests a fundamental limitation with programmatic initialization")
    log.close()
    sys.exit(1)

# Now try to add a component
log_print("\n[3] Adding Component...")
try:
    comp_node = aspen.Tree.FindNode(r"\Data\Components\Specifications\Input\CAG_IDS")
    comp_node.Elements.Add("WATER")
    log_print("[OK] WATER added")
except Exception as e:
    log_print(f"[FAIL] {e}")

# Set property method
log_print("\n[4] Setting Property Method...")
try:
    method_node = aspen.Tree.FindNode(r"\Data\Properties\Global\Input\METHOD")
    if method_node:
        method_node.Value = "IDEAL"
        log_print("[OK] Set to IDEAL")
    else:
        log_print("[FAIL] METHOD node not found")
except Exception as e:
    log_print(f"[FAIL] {e}")

# Create streams
log_print("\n[5] Creating Streams...")
try:
    streams = aspen.Tree.FindNode(r"\Data\Streams")
    for stream in ["WATER1", "WATER2", "OUT"]:
        streams.Elements.Add(stream)
        log_print(f"[OK] {stream}")
except Exception as e:
    log_print(f"[FAIL] {e}")

# CRITICAL TEST: Try RootModel method
log_print("\n[6] Exploring RootModel...")
log_print("-"*70)

try:
    app = aspen.Application
    if hasattr(app, 'RootModel'):
        root_model = app.RootModel
        log_print(f"  [OK] RootModel: {root_model}")
        
        # Check what methods RootModel has
        methods = [m for m in dir(root_model) if not m.startswith('_')]
        log_print(f"  RootModel has {len(methods)} methods")
        
        # Look for block-related methods
        block_methods = [m for m in methods if 'block' in m.lower()]
        if block_methods:
            log_print(f"  Block-related methods: {block_methods}")
            
except Exception as e:
    log_print(f"  [ERROR] {e}")

# Try using win32com dynamic dispatch
log_print("\n[7] Trying Dynamic Dispatch...")
log_print("-"*70)

try:
    # Maybe we need to use dynamic dispatch
    aspen_dynamic = win32.dynamic.Dispatch("Apwn.Document")
    log_print("  [OK] Dynamic dispatch created")
    
    # Try to access existing aspen's tree through dynamic
    # This is a long shot but worth trying
    
except Exception as e:
    log_print(f"  [INFO] {e}")

# LAST RESORT: Check if we can use SendKeys or similar
log_print("\n[8] Checking for UI Automation possibilities...")
log_print("-"*70)

log_print("  Note: UI automation (SendKeys, pyautogui) would be possible")
log_print("  but goes against the requirement of no manual GUI interaction")

log_print("\n" + "="*70)
log_print("FINAL CONCLUSION")
log_print("="*70)

log_print("\nBased on all research:")
log_print("1. InitNew() creates a minimal tree structure")
log_print("2. Components and Streams nodes work fine")
log_print("3. Blocks.Elements.Add() ALWAYS fails with 'Invalid Block/Model/Library'")
log_print("4. This appears to be a limitation of the COM interface")
log_print("5. Blocks may require:")
log_print("   - A specific library to be loaded first")
log_print("   - A different API method we haven't found")
log_print("   - Manual creation in GUI (which you want to avoid)")
log_print("\nRecommendation: Use a template file with pre-created blocks")

log.close()
print("\n✓ Check final_research_log.txt for complete findings")
