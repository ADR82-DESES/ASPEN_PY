"""
RESEARCH: Library and Model Discovery
Searching for library-related nodes in the tree and testing different Add patterns
"""
import win32com.client as win32
import sys
import time

log = open("library_research_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS LIBRARY RESEARCH")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    aspen.Visible = True
    
    # Search for "Library" in the tree
    log_print("\n[1] Searching Tree for 'Library' keywords...")
    
    def search_tree(node, depth=0, max_depth=4):
        if depth > max_depth: return
        try:
            if "Library" in node.Name or "Model" in node.Name:
                log_print(f"  {'  '*depth}Found: {node.Name} at {node.Path}")
            
            if hasattr(node, 'Elements'):
                for i in range(node.Elements.Count):
                    search_tree(node.Elements.Item(i), depth + 1, max_depth)
        except:
            pass

    search_tree(aspen.Tree.FindNode(r"\Data"))

    # Test Alternate Add patterns
    log_print("\n[2] Testing Alternate Add patterns for Blocks...")
    blocks = aspen.Tree.FindNode(r"\Data\Blocks")
    
    # Try different second arguments
    test_types = [
        "MIXER",
        "Mixer.Mixer",
        "Built-In.Mixer",
        "User Models.Mixer",
        "AP-Models.Mixer",
        "AP-Models.Mixer.1",
        "{B85A0D20-2E85-11D1-A9AD-00A0247C0F4A}" # Random CLSID check
    ]

    for t in test_types:
        log_print(f"  Trying Elements.Add('M1', '{t}')...")
        try:
            blocks.Elements.Add("M1", t)
            log_print(f"    [SUCCESS] Block created with type {t}")
            break
        except Exception as e:
            log_print(f"    [FAIL] {str(e)[:100]}")

    # Check for "Execute" methods on the main object
    log_print("\n[3] Checking for Execute/Run methods...")
    methods = [m for m in dir(aspen) if any(kw in m.lower() for keyword in ['execute', 'run', 'script', 'command'])]
    log_print(f"  Found: {methods}")

    for m in methods:
        log_print(f"  Method {m} exists")

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
