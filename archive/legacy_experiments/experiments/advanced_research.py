"""
ADVANCED API RESEARCH: Type Library Exploration
Using EnsureDispatch to reveal hidden methods and testing UnitOpCollection
"""
import win32com.client as win32
import sys
import traceback

log = open("advanced_api_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ADVANCED ASPEN PLUS API RESEARCH")
log_print("="*70)

# Target ProgIDs
targets = [
    "AspenTech.Framework.UnitOpCollection",
    "AspenTech.AspenPlus.PfsDialogs.PFSFlowsheetDialogs.400",
    "AspenTech.AspenPlus.HybridModelLibManager.40.0",
    "AspenTech.Modeler.ACMExpLibManager.40.0"
]

log_print("\n[1] Exploring with EnsureDispatch...")
log_print("-"*70)

for prog_id in targets:
    log_print(f"\nTrying EnsureDispatch: {prog_id}")
    try:
        # Use EnsureDispatch to generate Python wrappers from type library
        obj = win32.gencache.EnsureDispatch(prog_id)
        log_print(f"  [SUCCESS] Created: {obj}")
        
        # Now dir() should show much more
        methods = [m for m in dir(obj) if not m.startswith('_')]
        log_print(f"  Methods ({len(methods)}): {methods[:20]}")
        if len(methods) > 20:
             log_print(f"    ... {len(methods)-20} more")
             
    except Exception as e:
        log_print(f"  [INFO] EnsureDispatch failed, falling back to Dispatch: {e}")
        try:
            obj = win32.Dispatch(prog_id)
            log_print(f"  [SUCCESS] Created via Dispatch: {obj}")
            methods = [m for m in dir(obj) if not m.startswith('_')]
            log_print(f"  Methods: {methods}")
        except Exception as e2:
            log_print(f"  [FAIL] {e2}")

# Test UnitOpCollection specifically
log_print("\n[2] Deep Dive: UnitOpCollection.add")
log_print("-"*70)

try:
    coll = win32.Dispatch("AspenTech.Framework.UnitOpCollection")
    log_print("Testing UnitOpCollection.add with different argument patterns...")
    
    patterns = [
        ("MIXER",),
        ("MIXER", "Mixer"),
        ("Mixer", "MIXER"),
        (1, "MIXER"),
        ("MIXER", 1)
    ]
    
    for p in patterns:
        log_print(f"  Trying add{p}...")
        try:
            # We need to know if it's connected to a document
            # Usually these collections are obtained FROM a document
            res = coll.add(*p)
            log_print(f"    [SUCCESS] Result: {res}")
        except Exception as e:
            log_print(f"    [FAIL] {str(e)[:100]}")
            
except Exception as e:
    log_print(f"Error testing UnitOpCollection: {e}")

# Strategy: Get collections FROM the document
log_print("\n[3] Searching for collections in Apwn.Document...")
log_print("-"*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    
    # Check for hidden or undocumented collections
    # Some older Aspen APIs used 'Flowsheet' or 'Application' objects
    
    if hasattr(aspen, 'Application'):
        app = aspen.Application
        log_print(f"Application object found: {app}")
        
        # Check for ModelManager or LibraryManager on Application
        for attr in ['ModelManager', 'LibraryManager', 'ModelLibrary', 'UnitOps']:
            try:
                val = getattr(app, attr, None)
                if val:
                    log_print(f"  Found {attr}: {val}")
                    log_print(f"  Methods: {[m for m in dir(val) if not m.startswith('_')]}")
            except:
                pass

    # Try to find the UnitOpCollection from the Flowshet
    # Research says there might be a 'Blocks' or 'UnitOperations' collection
    
except Exception as e:
    log_print(f"Error accessing application: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
