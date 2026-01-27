"""
RESEARCH: Comprehensive API Discovery
Searching for ANY CLSID that looks like a simulation entry point
"""
import winreg
import win32com.client as win32

log = open("com_discovery_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("COMPREHENSIVE COM API DISCOVERY")
log_print("="*70)

keywords = ["simulation", "flowsheet", "aspenplus", "apwn", "engine", "document", "application"]
found_progids = set()

try:
    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "") as root:
        for i in range(100000): # Scan many
            try:
                progid = winreg.EnumKey(root, i)
                lower_progid = progid.lower()
                
                # Look for versioned progids like AspenPlus.Simulation.40.0
                if any(kw in lower_progid for kw in keywords):
                    if "aspen" in lower_progid or "apwn" in lower_progid:
                        found_progids.add(progid)
            except OSError:
                break
except Exception as e:
    log_print(f"Error scanning registry: {e}")

log_print(f"Found {len(found_progids)} potential ProgIDs.")

# Test the most promising ones
promising_patterns = [
    "Simulation",
    "Application",
    "Engine",
    "Flowsheet",
    "Document"
]

for progid in sorted(list(found_progids)):
    if any(p in progid for p in promising_patterns):
        log_print(f"\nTesting: {progid}")
        try:
            # Try to connect without creating new instance if possible
            try:
                obj = win32.GetActiveObject(progid)
                log_print("  [SUCCESS] Connected to active object")
            except:
                obj = win32.Dispatch(progid)
                log_print("  [SUCCESS] Created new instance")
            
            methods = [m for m in dir(obj) if not m.startswith("_")]
            log_print(f"  Methods: {methods[:10]}")
            if "Add" in methods or "Create" in methods:
                log_print(f"  *** INTERESTING METHODS FOUND: {[m for m in methods if 'Add' in m or 'Create' in m]} ***")
                
        except Exception as e:
            # log_print(f"  [FAIL] {str(e)[:100]}")
            pass

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
