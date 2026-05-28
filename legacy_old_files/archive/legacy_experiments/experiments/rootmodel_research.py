"""
RESEARCH: Calling RootModel and exploring LibRef
"""
import win32com.client as win32
import time

log = open("rootmodel_research_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS ROOTMODEL RESEARCH")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(5)
    
    app = aspen.Application
    
    # [1] Calling RootModel()
    log_print("\n[1] Calling app.RootModel()...")
    try:
        root = app.RootModel()
        log_print(f"  Root object: {root}")
        # Use dir() to see what it has
        methods = [m for m in dir(root) if not m.startswith('_')]
        log_print(f"  Methods: {methods}")
        
        # If it has a collection of blocks or libraries, let's see
        for attr in ['Blocks', 'Libraries', 'Elements', 'Children']:
            try:
                val = getattr(root, attr)
                log_print(f"  {attr} found: {val}")
                if hasattr(val, 'Count'):
                    log_print(f"    Count: {val.Count}")
            except:
                pass
    except Exception as e:
        log_print(f"  RootModel call error: {e}")

    # [2] Exploring LibRef
    log_print("\n[2] Exploring LibRef in detail...")
    try:
        libref = aspen.LibRef
        log_print(f"  LibRef: {libref}")
        methods = [m for m in dir(libref) if not m.startswith('_')]
        log_print(f"  LibRef methods: {methods}")
        
        # Check Elements on LibRef
        if hasattr(libref, 'Elements'):
            count = libref.Elements.Count
            log_print(f"  LibRef elements count: {count}")
            for i in range(min(10, count)):
                 log_print(f"    - Item({i}): {libref.Elements.Item(i).Name}")
    except Exception as e:
        log_print(f"  LibRef exploration error: {e}")

    # [3] Searching for "Mixer" in LibRef
    log_print("\n[3] Searching for 'Mixer' in LibRef...")
    try:
        if hasattr(libref, 'Elements'):
            for i in range(libref.Elements.Count):
                item = libref.Elements.Item(i)
                if "Mixer" in item.Name or "MIXER" in item.Name:
                    log_print(f"  FOUND: {item.Name} at index {i}")
                    # What is this item?
                    log_print(f"    Methods: {[m for m in dir(item) if not m.startswith('_')]}")
    except:
        pass

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
