"""
RESEARCH: Drilling down into LibRef Categories
Testing Enum and looking for Model names
"""
import win32com.client as win32
import time
import pythoncom

log = open("libref_drilldown_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS LIBREF DRILLDOWN")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(5)
    
    libref = aspen.LibRef
    
    # [1] Testing Enum with various indexes (category indexes)
    log_print("\n[1] Testing Enum with category indexes...")
    for i in range(7):
        log_print(f"Testing Enum({i})...")
        try:
            # Use VARIANT for low level just in case
            v_i = win32.VARIANT(pythoncom.VT_I4, i)
            res = libref.Enum(v_i)
            log_print(f"  Result: {res}")
            if res:
                 methods = [m for m in dir(res) if not m.startswith('_')]
                 log_print(f"  Methods: {methods[:15]}")
                 
                 # Maybe it's a collection?
                 if hasattr(res, 'Count'):
                      log_print(f"  Count: {res.Count}")
                      for j in range(min(10, res.Count)):
                           try:
                                item = res.Item(j)
                                log_print(f"    - Item({j}): {item.Name} | Value: {item.Value if hasattr(item, 'Value') else 'N/A'}")
                           except:
                                pass
        except Exception as e:
            log_print(f"  Enum({i}) error: {e}")

    # [2] Category-based Add attempts
    log_print("\n[2] Testing Add with category info...")
    blocks = aspen.Tree.FindNode(r"\Data\Blocks")
    
    attempts = [
        ("B1", "MIXER", "Mixers/Splitters"),
        ("B2", "Mixer", "Mixers/Splitters"),
        ("B3", "MIXER", "Built-In"),
        ("B4", "MIXER", "Built-In|Mixers/Splitters"),
        ("B5", "Mixers/Splitters.MIXER", ""),
    ]
    
    for name, model, lib in attempts:
        log_print(f"  Trying Add('{name}', '{model}', '{lib}')...")
        try:
             # Try 3-arg first via low level invoke if needed
             dispid = blocks.Elements._oleobj_.GetIDsOfNames("Add")
             try:
                 res = blocks.Elements._oleobj_.Invoke(dispid, 0, pythoncom.DISPATCH_METHOD, True, name, model, lib)
                 log_print(f"    [SUCCESS] Invoke returned: {res}")
             except Exception as e:
                 log_print(f"    [FAIL] Invoke: {str(e)[:100]}")
        except:
             pass

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
