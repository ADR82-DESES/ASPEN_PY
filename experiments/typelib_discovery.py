"""
RESEARCH: Finding Apwn.Document TypeLib
Getting the TypeLib GUID from the Registry
"""
import winreg

log = open("typelib_discovery_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

try:
    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "Apwn.Document\\CLSID") as key:
        clsid = winreg.QueryValue(key, None)
        log_print(f"Apwn.Document CLSID: {clsid}")
        
    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"CLSID\\{clsid}\\TypeLib") as key:
        typelib_guid = winreg.QueryValue(key, None)
        log_print(f"TypeLib GUID: {typelib_guid}")
        
    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"TypeLib\\{typelib_guid}") as key:
        # Enumerate versions
        try:
            version = winreg.EnumKey(key, 0)
            log_print(f"Version: {version}")
            with winreg.OpenKey(key, f"{version}\\0\\win32") as subkey:
                path = winreg.QueryValue(subkey, None)
                log_print(f"Path: {path}")
            with winreg.OpenKey(key, f"{version}\\0\\win64") as subkey:
                path64 = winreg.QueryValue(subkey, None)
                log_print(f"Path (win64): {path64}")
        except:
             pass

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
