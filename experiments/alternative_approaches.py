"""
ALTERNATIVE APPROACH: Use Aspen Plus Engine Methods
Instead of Elements.Add(), try using the Engine or Application methods
"""
import win32com.client as win32
import sys

log = open("alternative_approach_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ALTERNATIVE BLOCK CREATION APPROACH")
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

# Add component first
log_print("\n[2] Adding Component...")
try:
    aspen.Tree.FindNode(r"\Data\Components\Specifications\Input\CAG_IDS").Elements.Add("WATER")
    log_print("[OK] WATER component added")
except Exception as e:
    log_print(f"[INFO] {e}")

# Set property method
log_print("\n[3] Setting Property Method...")
try:
    aspen.Tree.FindNode(r"\Data\Properties\Global\Input\METHOD").Value = "IDEAL"
    log_print("[OK] Property method set")
except Exception as e:
    log_print(f"[WARN] {e}")

# Try creating streams first (this works)
log_print("\n[4] Creating Streams...")
try:
    streams = aspen.Tree.FindNode(r"\Data\Streams")
    for stream in ["WATER1", "WATER2", "OUT"]:
        streams.Elements.Add(stream)
        log_print(f"[OK] {stream}")
except Exception as e:
    log_print(f"[ERROR] {e}")

# ALTERNATIVE 1: Try using ExecuteMenuCommand
log_print("\n[5] Alternative 1: ExecuteMenuCommand...")
log_print("-"*70)

try:
    if hasattr(aspen, 'ExecuteMenuCommand'):
        log_print("  Has ExecuteMenuCommand method")
        # Try to execute the menu command to add a mixer
        # Common menu paths: "Insert|Block|Mixer"
        try:
            aspen.ExecuteMenuCommand("Insert|Block|Mixer")
            log_print("  [SUCCESS] ExecuteMenuCommand worked!")
        except Exception as e:
            log_print(f"  [FAIL] {e}")
    else:
        log_print("  No ExecuteMenuCommand method")
except Exception as e:
    log_print(f"  [ERROR] {e}")

# ALTERNATIVE 2: Try using Application.Invoke or similar
log_print("\n[6] Alternative 2: Check Application methods...")
log_print("-"*70)

try:
    app = aspen.Application
    log_print(f"  Application: {app}")
    
    # List all methods
    methods = [m for m in dir(app) if not m.startswith('_')]
    log_print(f"  Application has {len(methods)} methods")
    
    # Look for useful ones
    useful_methods = [m for m in methods if any(keyword in m.lower() for keyword in ['add', 'create', 'insert', 'block', 'model'])]
    
    if useful_methods:
        log_print(f"  Potentially useful methods: {useful_methods}")
    
except Exception as e:
    log_print(f"  [ERROR] {e}")

# ALTERNATIVE 3: Try accessing Blocks node differently
log_print("\n[7] Alternative 3: Different Blocks node access...")
log_print("-"*70)

try:
    # Maybe we need to access a different path
    alt_paths = [
        r"\Data\Blocks\Input",
        r"\Data\Flowsheet\Blocks",
        r"\Flowsheet\Blocks",
    ]
    
    for path in alt_paths:
        log_print(f"\nTrying: {path}")
        try:
            node = aspen.Tree.FindNode(path)
            if node:
                log_print(f"  [FOUND] Node exists")
                
                # Try to add
                try:
                    node.Elements.Add("MIXER", "Mixer")
                    log_print(f"  [SUCCESS] Add worked at this path!")
                except Exception as e:
                    log_print(f"  [FAIL] {str(e)[:80]}")
            else:
                log_print(f"  [NOT FOUND]")
        except Exception as e:
            log_print(f"  [ERROR] {str(e)[:80]}")
            
except Exception as e:
    log_print(f"[ERROR] {e}")

# ALTERNATIVE 4: Try using only block name without type
log_print("\n[8] Alternative 4: Add block without specifying type...")
log_print("-"*70)

try:
    blocks = aspen.Tree.FindNode(r"\Data\Blocks")
    
    # Just add with name only
    log_print("Trying: Elements.Add('MIXER') with no type")
    try:
        blocks.Elements.Add("MIXER")
        log_print("  [SUCCESS] Block added without type!")
        
        # Check if it was created
        mixer = aspen.Tree.FindNode(r"\Data\Blocks\MIXER")
        if mixer:
            log_print("  [VERIFIED] MIXER exists")
            
            # Now try to set the type
            log_print("  Trying to set TYPE property...")
            try:
                input_node = mixer.FindNode("Input")
                if input_node:
                    # Try to add TYPE node
                    try:
                        type_node = input_node.FindNode("TYPE")
                        if type_node:
                            type_node.Value = "Mixer"
                            log_print("  [SUCCESS] Set TYPE to Mixer!")
                        else:
                            log_print("  [INFO] TYPE node doesn't exist yet")
                            # Maybe we need to create it?
                    except Exception as e:
                        log_print(f"  [FAIL] {e}")
            except Exception as e:
                log_print(f"  [ERROR] {e}")
    except Exception as e:
        log_print(f"  [FAIL] {str(e)[:100]}")
        
except Exception as e:
    log_print(f"[ERROR] {e}")

# ALTERNATIVE 5: Check if we need to use a template file
log_print("\n[9] Alternative 5: Using Template Files...")
log_print("-"*70)

log_print("Checking if InitFromTemplate2 can help...")
try:
    # Common Aspen Plus template locations
    import os
    
    # Try to find Aspen Plus installation
    possible_paths = [
        r"C:\Program Files\AspenTech\Aspen Plus V40\GUI\Templates",
        r"C:\Program Files (x86)\AspenTech\Aspen Plus V40\GUI\Templates",
        r"C:\Program Files\AspenTech\Aspen Plus V12\GUI\Templates",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            log_print(f"  [FOUND] Template directory: {path}")
            
            # List .apw files
            try:
                files = [f for f in os.listdir(path) if f.endswith('.apw')]
                log_print(f"  Found {len(files)} template files")
                if files:
                    log_print(f"  Examples: {files[:5]}")
            except:
                pass
        else:
            log_print(f"  [NOT FOUND] {path}")
            
except Exception as e:
    log_print(f"  [ERROR] {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)

log.close()
print("\n✓ Check alternative_approach_log.txt for results")
