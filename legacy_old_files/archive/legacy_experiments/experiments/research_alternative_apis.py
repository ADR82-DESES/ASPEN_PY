"""
RESEARCH: Alternative Aspen Plus APIs
Exploring different COM interfaces and automation methods
"""
import win32com.client as win32
import sys

log = open("alternative_apis_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ALTERNATIVE ASPEN PLUS APIs RESEARCH")
log_print("="*70)

# Known Aspen Plus COM ProgIDs
prog_ids = [
    "Apwn.Document",           # Standard document interface (what we've been using)
    "Aspen.Document",          # Alternative document interface
    "AspenPlus.Document",      # Full name variant
    "Apwn.Application",        # Application interface
    "Aspen.Application",       # Alternative application
    "AspenPlus.Application",   # Full application name
    "AES.Document",            # Aspen Engineering Suite
    "AES.Application",         # AES Application
    "Aspen.Flowsheet",         # Flowsheet interface
    "Aspen.Simulation",        # Simulation interface
]

log_print("\n[1] Testing Different COM ProgIDs...")
log_print("-"*70)

successful_interfaces = []

for prog_id in prog_ids:
    log_print(f"\nTrying: {prog_id}")
    try:
        obj = win32.Dispatch(prog_id)
        log_print(f"  [SUCCESS] Created object: {obj}")
        
        # Try to get more info
        try:
            if hasattr(obj, 'Name'):
                log_print(f"  Name: {obj.Name}")
            if hasattr(obj, 'Version'):
                log_print(f"  Version: {obj.Version}")
        except:
            pass
        
        # List methods
        methods = [m for m in dir(obj) if not m.startswith('_')]
        log_print(f"  Has {len(methods)} methods")
        
        # Look for promising methods
        block_methods = [m for m in methods if any(kw in m.lower() for kw in ['block', 'model', 'unit', 'flowsheet'])]
        if block_methods:
            log_print(f"  Block-related methods: {block_methods[:10]}")
        
        successful_interfaces.append((prog_id, obj))
        
    except Exception as e:
        log_print(f"  [FAIL] {str(e)[:80]}")

# Test each successful interface for block creation
log_print("\n[2] Testing Block Creation with Each Interface...")
log_print("-"*70)

for prog_id, obj in successful_interfaces:
    log_print(f"\nTesting: {prog_id}")
    
    # Try to initialize
    try:
        if hasattr(obj, 'InitNew'):
            obj.InitNew()
            log_print("  [OK] InitNew() worked")
            
            # Try to access tree
            if hasattr(obj, 'Tree'):
                tree = obj.Tree
                log_print("  [OK] Has Tree")
                
                # Try to add a block
                try:
                    blocks = tree.FindNode(r"\Data\Blocks")
                    if blocks:
                        log_print("  [OK] Found Blocks node")
                        
                        # Try different add methods
                        try:
                            blocks.Elements.Add("TEST", "MIXER")
                            log_print("  [SUCCESS!] Block creation worked!")
                            log_print(f"\n*** SOLUTION FOUND: Use {prog_id} ***\n")
                        except Exception as e:
                            log_print(f"  [FAIL] Elements.Add: {str(e)[:60]}")
                except Exception as e:
                    log_print(f"  [ERROR] {e}")
        else:
            log_print("  [INFO] No InitNew method")
    except Exception as e:
        log_print(f"  [ERROR] {str(e)[:80]}")

# Check for Aspen Simulation Engine (different from GUI)
log_print("\n[3] Checking for Aspen Simulation Engine...")
log_print("-"*70)

engine_prog_ids = [
    "Apwn.SimulationEngine",
    "Aspen.SimulationEngine", 
    "AspenPlus.Engine",
    "Apwn.Engine",
]

for prog_id in engine_prog_ids:
    log_print(f"\nTrying: {prog_id}")
    try:
        engine = win32.Dispatch(prog_id)
        log_print(f"  [SUCCESS] Found: {engine}")
        
        methods = [m for m in dir(engine) if not m.startswith('_')]
        log_print(f"  Methods: {len(methods)}")
        
        # Look for useful methods
        useful = [m for m in methods if any(kw in m.lower() for kw in ['run', 'load', 'create', 'init'])]
        if useful:
            log_print(f"  Useful methods: {useful}")
            
    except Exception as e:
        log_print(f"  [FAIL] {str(e)[:60]}")

# Check for ActiveX/OLE automation alternatives
log_print("\n[4] Checking for Aspen Plus Automation Server...")
log_print("-"*70)

automation_ids = [
    "AspenPlus.AutomationServer",
    "Apwn.AutomationServer",
    "Aspen.AutomationServer",
]

for prog_id in automation_ids:
    log_print(f"\nTrying: {prog_id}")
    try:
        auto = win32.Dispatch(prog_id)
        log_print(f"  [SUCCESS] Found: {auto}")
        
        methods = [m for m in dir(auto) if not m.startswith('_')]
        log_print(f"  Methods: {methods[:20]}")
        
    except Exception as e:
        log_print(f"  [FAIL] {str(e)[:60]}")

# Check Windows Registry for all Aspen-related ProgIDs
log_print("\n[5] Scanning Windows Registry for Aspen ProgIDs...")
log_print("-"*70)

try:
    import winreg
    
    # Open HKEY_CLASSES_ROOT
    root_key = winreg.HKEY_CLASSES_ROOT
    
    aspen_prog_ids = []
    
    # Enumerate all ProgIDs
    try:
        i = 0
        while True:
            try:
                key_name = winreg.EnumKey(root_key, i)
                if any(keyword in key_name.lower() for keyword in ['aspen', 'apwn', 'aes']):
                    # Check if it has a CLSID (is a valid ProgID)
                    try:
                        key = winreg.OpenKey(root_key, key_name + "\\CLSID")
                        aspen_prog_ids.append(key_name)
                        winreg.CloseKey(key)
                    except:
                        pass
                i += 1
            except OSError:
                break
    except Exception as e:
        log_print(f"  [ERROR] {e}")
    
    if aspen_prog_ids:
        log_print(f"  Found {len(aspen_prog_ids)} Aspen-related ProgIDs:")
        for prog_id in aspen_prog_ids[:20]:  # Show first 20
            log_print(f"    - {prog_id}")
        
        if len(aspen_prog_ids) > 20:
            log_print(f"    ... and {len(aspen_prog_ids) - 20} more")
    else:
        log_print("  No Aspen ProgIDs found in registry")
        
except Exception as e:
    log_print(f"  [ERROR] {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)

if successful_interfaces:
    log_print(f"\nFound {len(successful_interfaces)} working interfaces")
    log_print("Check log for details on block creation capabilities")
else:
    log_print("\nNo alternative interfaces found")
    log_print("Apwn.Document appears to be the only available interface")

log.close()
print("\n✓ Check alternative_apis_log.txt for complete results")
