"""
RESEARCH: Searching for Mixer CLSID in Registry
"""
import winreg

log = open("clsid_mixer_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS CLSID MIXER SEARCH")
log_print("="*70)

try:
    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "CLSID") as root:
        for i in range(10000): # Check first 10000 CLSIDs
            try:
                clsid = winreg.EnumKey(root, i)
                try:
                    with winreg.OpenKey(root, clsid) as key:
                        val = winreg.QueryValue(key, None)
                        if val and "Aspen" in val and "Mixer" in val:
                            log_print(f"CLSID: {clsid} | Value: {val}")
                except:
                    pass
            except OSError:
                break
except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
