"""
RESEARCH: Contextual Block Creation
Selecting Category in LibRef before adding the block
"""
import win32com.client as win32
import time

log = open("contextual_add_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS CONTEXTUAL ADD RESEARCH")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(5)
    aspen.Visible = True
    
    libref = aspen.LibRef
    
    # [1] Select Category 0 (Mixers/Splitters)
    log_print("\n[1] Selecting Category 0 (Mixers/Splitters)...")
    try:
        # Based on methods: CategorySelected(index) -> Bool
        # Maybe it can also be used as a property setter?
        # or maybe there is a SelectCategory method?
        # Let's try to set it via OLE
        dispid = libref._oleobj_.GetIDsOfNames("CategorySelected")
        # Try both Get (0 index) and Put (1 index?)
        # For VARIANT(True), VT_BOOL = 11
        import pythoncom
        try:
             libref._oleobj_.Invoke(dispid, 0, pythoncom.DISPATCH_PROPERTYPUT, True, 0, True)
             log_print("  Successfully set CategorySelected(0) = True")
        except Exception as e:
             log_print(f"  Fail set CategorySelected: {e}")

        # [2] Try to Add now
        log_print("\n[2] Attempting Add('B1', 'Mixer')...")
        blocks = aspen.Tree.FindNode(r"\Data\Blocks")
        try:
             blocks.Elements.Add("B1", "Mixer")
             log_print("  [SUCCESS!!!] Block created after category selection!")
        except Exception as e:
             log_print(f"  [FAIL] {str(e)[:100]}")

    except Exception as e:
        log_print(f"Error: {e}")

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
