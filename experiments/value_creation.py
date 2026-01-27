"""
RESEARCH: Block Creation via Value Property
Testing if setting the Value of a block node defines its model type
"""
import win32com.client as win32
import time

log = open("value_creation_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS VALUE CREATION RESEARCH")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(5)
    aspen.Visible = True
    aspen.SuppressDialogs = 1
    
    blocks = aspen.Tree.FindNode(r"\Data\Blocks")
    
    log_print("\n[1] Testing Elements.Add('B1') then B1.Value = 'MIXER'...")
    try:
        # Try to add without type first
        try:
             b1 = blocks.Elements.Add("B1")
             log_print("  [OK] Added B1 (untyped)")
        except Exception as e:
             log_print(f"  [INFO] Elements.Add('B1') requires type? {e}")
             # If it requires type, maybe we can use a dummy?
             b1 = blocks.Elements.Add("B1", "MIXER") # This failed before
        
        if b1:
             b1.Value = "MIXER"
             log_print("  [OK] Set B1.Value = 'MIXER'")
             
             # Check if Input node appeared (this would mean it's initialized)
             time.sleep(1)
             if b1.FindNode("Input"):
                  log_print("  [VERIFIED] Input node found! Mixer created!")
             else:
                  log_print("  [FAILED] Input node not found")
    except Exception as e:
        log_print(f"  [FAIL] {e}")

    log_print("\n[2] Testing if we can find 'MIXER' in the Model Library...")
    # Maybe we can find the models in the tree under some other node
    
except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
