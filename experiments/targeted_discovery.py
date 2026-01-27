"""
RESEARCH: Targeted Registry Search for Simulation Objects
Looking for CLSIDs that provide the actual Simulation interfaces
"""
import winreg
import win32com.client as win32

log = open("targeted_discovery_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("TARGETED COM DISCOVERY")
log_print("="*70)

# Potential interfaces to look for in registry
target_interfaces = [
    "IAsimulation",
    "IAsimulationDoc",
    "IAflowsheet",
    "IAunitop",
    "IAblock",
    "IAcollection"
]

try:
    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "Interface") as root:
        for i in range(200000):
            try:
                iid = winreg.EnumKey(root, i)
                try:
                    with winreg.OpenKey(root, iid) as key:
                        val = winreg.QueryValue(key, None)
                        if val and any(target.lower() in val.lower() for target in target_interfaces):
                            log_print(f"Interface: {val} | IID: {iid}")
                except:
                    pass
            except OSError:
                break
except Exception as e:
    log_print(f"Error: {e}")

log_print("\nSearching for ProgIDs ending in .Simulation or .Application...")
try:
    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "") as root:
        for i in range(100000):
            try:
                progid = winreg.EnumKey(root, i)
                if (".Simulation" in progid or ".Application" in progid) and "aspen" in progid.lower():
                    log_print(f"ProgID: {progid}")
            except OSError:
                break
except:
    pass

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
