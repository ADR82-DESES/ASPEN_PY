"""
RESEARCH: Import Method for Block Creation (Fixed Init)
Testing the Import method with a snippet of Aspen Plus Input Language
"""
import win32com.client as win32
import os
import time

log = open("import_research_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS IMPORT RESEARCH")
log_print("="*70)

try:
    log_print("Connecting to Aspen...")
    aspen = win32.Dispatch("Apwn.Document")
    
    log_print("Initializing New Simulation...")
    aspen.InitNew()
    time.sleep(5)
    
    log_print("Setting properties...")
    aspen.Visible = True
    aspen.SuppressDialogs = 1
    
    # Create a tiny snippet file
    inp_file = os.path.abspath("block_snippet.inp")
    
    patterns = [
        ("B1", "BLOCK MIXER B1\n"),
        ("B2", "BLOCK MIXER B2 MIXER\n"),
        ("B3", "UNIT-OP MIXER B3\n")
    ]
    
    for name, content in patterns:
        log_print(f"\nTesting Import with content: {content.strip()}")
        with open(inp_file, "w") as f:
            f.write(content)
        
        try:
            # Test different methods
            if hasattr(aspen, "Import"):
                 log_print("  Calling Import...")
                 aspen.Import(inp_file)
            elif hasattr(aspen, "ImportSimulation"):
                 log_print("  Calling ImportSimulation...")
                 aspen.ImportSimulation(inp_file)
            
            log_print("  Call finished")
            time.sleep(3)
            
            # Check if created
            node = aspen.Tree.FindNode(rf"\Data\Blocks\{name}")
            if node:
                log_print(f"  [VERIFIED] Block {name} created!")
            else:
                log_print(f"  [FAILED] {name} not found")
        except Exception as e:
            log_print(f"  [FAIL] {e}")

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
