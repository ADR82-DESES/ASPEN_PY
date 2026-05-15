"""
RESEARCH: Inspecting Existing Blocks
Loading a built-in example to see how blocks are defined
"""
import win32com.client as win32
import os
import time

log = open("inspect_blocks_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS BLOCK INSPECTION")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    example_path = r"C:\Program Files\AspenTech\Aspen Plus V14.0\Favorites\testprob.bkp"
    
    if os.path.exists(example_path):
        log_print(f"Loading example: {example_path}")
        aspen.InitFromArchive2(example_path)
        time.sleep(5)
        
        blocks = aspen.Tree.FindNode(r"\Data\Blocks")
        if blocks:
             count = blocks.Elements.Count
             log_print(f"Example has {count} blocks")
             for i in range(count):
                 b = blocks.Elements.Item(i)
                 log_print(f"  Block: {b.Name}")
                 
                 # Try to find the type/model
                 try:
                      # Exploration of the block node
                      def explore(node, depth=0):
                          if depth > 2: return
                          log_print(f"    {'  '*depth}Node: {node.Name}")
                          if hasattr(node, 'Value') and node.Value:
                               log_print(f"    {'  '*depth}  Value: {node.Value}")
                          
                          if hasattr(node, 'Elements'):
                              for j in range(node.Elements.Count):
                                  explore(node.Elements.Item(j), depth + 1)
                      
                      explore(b)
                 except:
                      pass
    else:
        log_print("Example file not found")

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
