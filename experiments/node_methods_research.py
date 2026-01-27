"""
RESEARCH: Node Methods for Block Creation
Testing Insert, CreateChild, and other methods on the Blocks node
"""
import win32com.client as win32
import time

log = open("node_methods_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS NODE METHODS RESEARCH")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(5)
    aspen.Visible = True
    aspen.SuppressDialogs = 1
    
    blocks_node = aspen.Tree.FindNode(r"\Data\Blocks")
    log_print(f"Blocks node: {blocks_node}")
    
    # List all methods of the node
    methods = [m for m in dir(blocks_node) if not m.startswith('_')]
    log_print(f"Methods: {methods}")
    
    # Test promising methods
    test_data = [
        ("Insert", ("MIXER", "B1")),
        ("Insert", ("Mixer", "B1")),
        ("CreateChild", ("B2",)),
        ("Add", ("B3", "MIXER")),
        ("New", ("B4", "MIXER"))
    ]
    
    for name, args in test_data:
        if name in methods:
            log_print(f"\nTesting {name}{args}...")
            try:
                method = getattr(blocks_node, name)
                res = method(*args)
                log_print(f"  [SUCCESS] Result: {res}")
                if aspen.Tree.FindNode(rf"\Data\Blocks\{args[0 if name != 'Insert' else 1]}"):
                    log_print(f"  [VERIFIED] Block created!")
            except Exception as e:
                log_print(f"  [FAIL] {str(e)[:100]}")
        else:
            log_print(f"\nMethod {name} not found on node")

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
