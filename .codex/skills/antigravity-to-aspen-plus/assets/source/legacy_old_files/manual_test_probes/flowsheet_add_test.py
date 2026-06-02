"""
RESEARCH: Testing Flowsheet-based Addition
"""
import win32com.client as win32
import time

def test():
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(10)
    aspen.Visible = True
    aspen.SuppressDialogs = 1

    paths = [
        r"\Data\Blocks",
        r"\Data\Flowsheet\Blocks",
        r"\Data\Flowsheet\Section\GLOBAL\Blocks",
        r"\Data\Flowsheet\Unit Operations"
    ]

    for p in paths:
        print(f"\nChecking path: {p}")
        node = aspen.Tree.FindNode(p)
        if node:
             print(f"  Found node! Elements count: {node.Elements.Count}")
             try:
                  node.Elements.Add("B1", "MIXER")
                  print(f"  [SUCCESS] Created Mixer at {p}")
                  return
             except Exception as e:
                  print(f"  [FAIL] {str(e)[:100]}")
        else:
             print("  Node not found.")

if __name__ == "__main__":
    test()
