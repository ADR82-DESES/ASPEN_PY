"""
RESEARCH: Node Import
Testing the Import method on the Blocks node itself
"""
import win32com.client as win32
import os
import time

log = open("node_import_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS NODE IMPORT RESEARCH")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(5)
    aspen.Visible = True
    aspen.SuppressDialogs = 1
    
    blocks_node = aspen.Tree.FindNode(r"\Data\Blocks")
    
    # Create a tiny snippet file
    inp_file = os.path.abspath("node_snippet.inp")
    with open(inp_file, "w") as f:
        # Try both .inp and .txt if needed
        # Format might be different for node import
        f.write("BLOCK MIXER B1\n")
    
    log_print(f"Testing blocks_node.Import('{inp_file}')...")
    try:
        # Using a variant for the string to avoid the COM conversion error
        import pythoncom
        path_variant = win32.VARIANT(pythoncom.VT_BSTR, inp_file)
        
        blocks_node.Import(path_variant)
        log_print("  [SUCCESS] node.Import called")
        time.sleep(2)
        
        if aspen.Tree.FindNode(r"\Data\Blocks\B1"):
             log_print("  [VERIFIED] Block B1 created!")
        else:
             log_print("  [FAILED] B1 not found")
    except Exception as e:
        log_print(f"  [FAIL] {e}")

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
