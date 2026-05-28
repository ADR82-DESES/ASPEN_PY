"""
RESEARCH: Comprehensive Block Node Exploration
Listing every single child node of a block to find where the type is stored
"""
import win32com.client as win32
import os
import time

log = open("deep_block_inspect_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS DEEP BLOCK INSPECTION")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    example_path = r"C:\Program Files\AspenTech\Aspen Plus V14.0\GUI\Examples\Hydrogen\Alkaline electrolysis\Industrial Scale Alkaline Electrolyzer\Industrial Scale Alkaline Electrolyzer.bkp"
    
    log_print(f"Loading: {example_path}")
    aspen.InitFromArchive2(example_path)
    time.sleep(5)
    
    blocks = aspen.Tree.FindNode(r"\Data\Blocks")
    if blocks and blocks.Elements.Count > 0:
        b = blocks.Elements.Item(0)
        log_print(f"Inspecting Block: {b.Name}")
        
        def deep_explore(node, path="", depth=0):
            if depth > 4: return
            try:
                name = node.Name
                full_path = path + "\\" + name
                val = ""
                try:
                    if hasattr(node, 'Value'): val = str(node.Value)
                except:
                    pass
                
                log_print(f"  {'  '*depth}{name} | Path: {full_path} | Value: {val}")
                
                if hasattr(node, 'Elements'):
                    for i in range(node.Elements.Count):
                        deep_explore(node.Elements.Item(i), full_path, depth + 1)
            except:
                pass

        deep_explore(b)
    else:
        log_print("No blocks found")

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
