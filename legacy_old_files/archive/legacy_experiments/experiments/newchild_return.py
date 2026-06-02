"""
RESEARCH: Testing NewChild return value
"""
import win32com.client as win32
import time

log = open("newchild_return_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS NEWCHILD RETURN RESEARCH")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(5)
    
    blocks_node = aspen.Tree.FindNode(r"\Data\Blocks")
    
    log_print("\nCalling blocks_node.NewChild('B1')...")
    res = blocks_node.NewChild("B1")
    log_print(f"Result type: {type(res)}")
    log_print(f"Result value: {res}")
    
    # If it's a string, maybe we can't use it directly.
    # But wait, node_deep_dive_log.txt said [SUCCESS] NewChild('B1') result: B1
    
    # Let's try to find it again with a slightly different path or after a delay
    time.sleep(2)
    b1 = aspen.Tree.FindNode(r"\Data\Blocks\B1")
    if b1:
         log_print("Found B1 after delay")
    else:
         log_print("B1 STILL NOT FOUND via FindNode")
         
         # Maybe it's in Elements?
         try:
              count = blocks_node.Elements.Count
              log_print(f"Blocks Elements count: {count}")
              for i in range(count):
                   log_print(f"  Item({i}): {blocks_node.Elements.Item(i).Name}")
         except:
              pass

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
