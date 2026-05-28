"""
RESEARCH: Advanced Node Methods (Deep Dive)
Testing NewChild, PFSSelectModel, and AppendTemplate on the Blocks node
"""
import win32com.client as win32
import time
import os

log = open("node_deep_dive_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS NODE DEEP DIVE")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(5)
    aspen.Visible = True
    aspen.SuppressDialogs = 1
    
    blocks_node = aspen.Tree.FindNode(r"\Data\Blocks")
    
    # [1] Testing NewChild
    log_print("\n[1] Testing NewChild()...")
    try:
        # NewChild usually takes the name of the new node
        res = blocks_node.NewChild("B1")
        log_print(f"  [SUCCESS] NewChild('B1') result: {res}")
        if aspen.Tree.FindNode(r"\Data\Blocks\B1"):
             log_print("  [VERIFIED] Node B1 created!")
             
             # Now try to set the model type via PFSSelectModel if it exists
             if hasattr(blocks_node, "PFSSelectModel"):
                  log_print("  Testing PFSSelectModel('MIXER')...")
                  try:
                       # Select B1 first?
                       aspen.Tree.FindNode(r"\Data\Blocks\B1").PFSSelectModel("MIXER")
                       log_print("    [SUCCESS] PFSSelectModel called")
                  except Exception as e:
                       log_print(f"    [FAIL] {e}")
    except Exception as e:
        log_print(f"  [FAIL] {e}")

    # [2] Testing AppendTemplate
    log_print("\n[2] Testing AppendTemplate()...")
    try:
        # Create a tiny .bkp or .inp or something?
        # Research says AppendTemplate might take a path to a partial file
        temp_file = os.path.abspath("tiny_mixer.inp")
        with open(temp_file, "w") as f:
            f.write("BLOCK MIXER B2\n")
            
        log_print(f"  Trying AppendTemplate('{temp_file}')...")
        try:
             blocks_node.AppendTemplate(temp_file)
             log_print("    [SUCCESS] AppendTemplate called")
             if aspen.Tree.FindNode(r"\Data\Blocks\B2"):
                  log_print("    [VERIFIED] Block B2 created!")
        except Exception as e:
             log_print(f"    [FAIL] {e}")
    except Exception as e:
        log_print(f"  [FAIL] {e}")

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
