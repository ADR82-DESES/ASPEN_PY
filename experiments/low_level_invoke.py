"""
RESEARCH: Low-level COM Invoke for Block Creation
Trying to bypass win32com wrapper and pass 3 arguments to Elements.Add
"""
import win32com.client as win32
import pythoncom
import time

log = open("low_level_invoke_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS LOW-LEVEL INVOKE RESEARCH")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(5)
    aspen.Visible = True
    aspen.SuppressDialogs = 1
    
    blocks = aspen.Tree.FindNode(r"\Data\Blocks")
    elements = blocks.Elements
    
    # Get the DISPID for 'Add'
    # We can use _oleobj_.GetIDsOfNames
    dispid = elements._oleobj_.GetIDsOfNames("Add")
    log_print(f"DISPID for Add: {dispid}")
    
    # Test 3-argument Invoke
    log_print("\nTesting 3-argument Invoke with 'Model Library'...")
    try:
        # Arguments are passed in REVERSE order to Invoke (or use specific flags)
        # But win32com.client.Dispatch's _oleobj_.Invoke handles it differently if we use positional
        
        # Invoke parameters: (dispid, lcid, flags, bWait, *args)
        # For Add: name, model, library
        res = elements._oleobj_.Invoke(dispid, 0, pythoncom.DISPATCH_METHOD, True, "B1", "MIXER", "Model Library")
        log_print(f"  [SUCCESS] Invoke returned: {res}")
        if aspen.Tree.FindNode(r"\Data\Blocks\B1"):
             log_print("  [VERIFIED] Block B1 created!")
    except Exception as e:
        log_print(f"  [FAIL] 3-argument Invoke: {e}")

    # Test 2-argument Invoke (just to be sure)
    log_print("\nTesting 2-argument Invoke...")
    try:
        res = elements._oleobj_.Invoke(dispid, 0, pythoncom.DISPATCH_METHOD, True, "B2", "MIXER")
        log_print(f"  [SUCCESS] Invoke returned: {res}")
    except Exception as e:
        log_print(f"  [FAIL] 2-argument Invoke: {e}")

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
