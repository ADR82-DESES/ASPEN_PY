"""
RESEARCH: Low-level Invoke for Engine.ProcessInput
"""
import win32com.client as win32
import pythoncom
import time

log = open("processinput_lowlevel_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS PROCESSINPUT LOW-LEVEL RESEARCH")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(5)
    
    engine = aspen.Engine
    
    # Get DISPID
    dispid = engine._oleobj_.GetIDsOfNames("ProcessInput")
    log_print(f"DISPID for ProcessInput: {dispid}")
    
    # Try to Invoke as Method
    log_print("\nTrying to Invoke ProcessInput as Method...")
    try:
         # For Aspen Engine, maybe it needs a specific flag
         res = engine._oleobj_.Invoke(dispid, 0, pythoncom.DISPATCH_METHOD, True, "BLOCK B1 MIXER")
         log_print(f"  [SUCCESS] Invoke returned: {res}")
         time.sleep(2)
         if aspen.Tree.FindNode(r"\Data\Blocks\B1"):
              log_print("  [VERIFIED] Block B1 created!")
    except Exception as e:
         log_print(f"  [FAIL] Method Invoke: {e}")

    # Try to Invoke as Property Put
    log_print("\nTrying to Invoke ProcessInput as Property Put...")
    try:
         res = engine._oleobj_.Invoke(dispid, 0, pythoncom.DISPATCH_PROPERTYPUT, True, "BLOCK B2 MIXER")
         log_print(f"  [SUCCESS] Invoke returned: {res}")
    except Exception as e:
         log_print(f"  [FAIL] Property Put Invoke: {e}")

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
