"""
RESEARCH: Create block via NewChild and setting Value
"""
import win32com.client as win32
import time

log = open("newchild_value_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS NEWCHILD+VALUE RESEARCH")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(5)
    aspen.Visible = True
    
    blocks_node = aspen.Tree.FindNode(r"\Data\Blocks")
    
    log_print("\n[1] Creating B1 via NewChild('B1')...")
    try:
        blocks_node.NewChild("B1")
        b1 = aspen.Tree.FindNode(r"\Data\Blocks\B1")
        if b1:
             log_print("  [OK] Node B1 created")
             
             # Try setting Value to various model types
             types = ["MIXER", "Mixer", "V-DRUM1", "Heater"]
             for t in types:
                  log_print(f"  Trying b1.Value = '{t}'...")
                  try:
                       b1.Value = t
                       log_print(f"    [OK] Value set to {t}")
                       time.sleep(2)
                       # Check for Input node
                       if b1.FindNode("Input"):
                            log_print(f"    [SUCCESS!!!] Input node appeared for type {t}")
                            break
                       else:
                            log_print("    [INFO] No Input node yet")
                  except Exception as e:
                       log_print(f"    [FAIL] {e}")
        else:
             log_print("  [FAIL] NewChild did not return/create B1?")
    except Exception as e:
        log_print(f"  [FAIL] NewChild error: {e}")

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
