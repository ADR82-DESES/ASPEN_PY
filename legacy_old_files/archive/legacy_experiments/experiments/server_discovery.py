"""
RESEARCH: Finding Apwn.Document Server Path
"""
import winreg

log = open("server_discovery_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

clsid = "{CF916C06-D17A-4A07-8548-787F4B0F99CB}"

try:
    for key_name in ["InprocServer32", "InprocHandler32", "LocalServer32"]:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"CLSID\\{clsid}\\{key_name}") as key:
                val = winreg.QueryValue(key, None)
                log_print(f"{key_name}: {val}")
        except:
             pass

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
