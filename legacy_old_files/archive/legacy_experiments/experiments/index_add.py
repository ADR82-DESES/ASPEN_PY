"""
RESEARCH: Testing Add with Index as Library
"""
import win32com.client as win32
import time
import pythoncom

log = open("index_add_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS INDEX ADD RESEARCH")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(5)
    aspen.Visible = True
    
    blocks = aspen.Tree.FindNode(r"\Data\Blocks").Elements
    dispid = blocks._oleobj_.GetIDsOfNames("Add")
    
    # [1] Testing with index 0
    log_print("\n[1] Testing Add('B1', 'Mixer', 0)...")
    try:
        # Note: Invoke uses positional arguments
        # For Add: Name, Model, Library
        res = blocks._oleobj_.Invoke(dispid, 0, pythoncom.DISPATCH_METHOD, True, "B1", "Mixer", 0)
        log_print(f"  [SUCCESS] Invoke returned: {res}")
    except Exception as e:
        log_print(f"  [FAIL] {e}")

    # [2] Testing with Category Index as part of model string?
    # Some docs say "ModelName|LibraryName"
    log_print("\n[2] Testing Add('B2', 'Mixer|Built-In')...")
    try:
        res = blocks._oleobj_.Invoke(dispid, 0, pythoncom.DISPATCH_METHOD, True, "B2", "Mixer|Built-In")
        log_print(f"  [SUCCESS] Invoke returned: {res}")
    except Exception as e:
        log_print(f"  [FAIL] {e}")

    # [3] Testing with exact category name
    log_print("\n[3] Testing Add('B3', 'Mixer', 'Mixers/Splitters')...")
    try:
        res = blocks._oleobj_.Invoke(dispid, 0, pythoncom.DISPATCH_METHOD, True, "B3", "Mixer", "Mixers/Splitters")
        log_print(f"  [SUCCESS] Invoke returned: {res}")
    except Exception as e:
        log_print(f"  [FAIL] {e}")

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
