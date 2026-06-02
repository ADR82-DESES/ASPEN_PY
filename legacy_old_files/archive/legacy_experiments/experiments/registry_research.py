"""
RESEARCH: Registry search for Mixer Models
"""
import winreg

log = open("registry_mixer_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS REGISTRY MIXER SEARCH")
log_print("="*70)

def search_registry(hkey, subkey, keyword):
    try:
        with winreg.OpenKey(hkey, subkey) as key:
            # Check values
            num_subkeys, num_values, modified = winreg.QueryInfoKey(key)
            for i in range(num_values):
                try:
                    name, value, type = winreg.EnumValue(key, i)
                    if isinstance(value, str) and keyword in value:
                        log_print(f"  Value Found | Key: {subkey} | Name: {name} | Value: {value}")
                except:
                    pass
            # Check subkeys
            for i in range(num_subkeys):
                try:
                    child_name = winreg.EnumKey(key, i)
                    if keyword in child_name:
                         log_print(f"  Key Found | {subkey}\\{child_name}")
                    search_registry(hkey, subkey + "\\" + child_name, keyword)
                except:
                    pass
    except:
        pass

# Search in relevant root keys
log_print("Searching HKEY_CLASSES_ROOT...")
search_registry(winreg.HKEY_CLASSES_ROOT, "AspenTech", "Mixer")
log_print("Searching HKEY_LOCAL_MACHINE\\SOFTWARE\\AspenTech...")
search_registry(winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\AspenTech", "Mixer")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
