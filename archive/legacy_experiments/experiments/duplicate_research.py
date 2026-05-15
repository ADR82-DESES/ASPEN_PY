"""
RESEARCH: Block Duplication
Testing if Elements.Add can duplicate an existing block
"""
import win32com.client as win32
import os
import time

log = open("duplicate_research_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS DUPLICATE RESEARCH")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    example_path = r"C:\Program Files\AspenTech\Aspen Plus V14.0\GUI\Examples\Hydrogen\Alkaline electrolysis\Industrial Scale Alkaline Electrolyzer\Industrial Scale Alkaline Electrolyzer.bkp"
    
    log_print(f"Loading: {example_path}")
    aspen.InitFromArchive2(example_path)
    time.sleep(5)
    
    blocks = aspen.Tree.FindNode(r"\Data\Blocks")
    if blocks and blocks.Elements.Count > 0:
        source_name = blocks.Elements.Item(0).Name
        log_print(f"Source block: {source_name}")
        
        log_print(f"Trying to duplicate {source_name} to B2 via Elements.Add('B2', '{source_name}')...")
        try:
             blocks.Elements.Add("B2", source_name)
             log_print("  [SUCCESS] Block B2 created!")
             if aspen.Tree.FindNode(r"\Data\Blocks\B2"):
                  log_print("  [VERIFIED] B2 exists in tree")
        except Exception as e:
             log_print(f"  [FAIL] {e}")
    else:
        log_print("No blocks found")

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
