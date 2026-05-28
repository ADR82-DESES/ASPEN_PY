import win32com.client as win32
import os

def check_node(aspen, path):
    try:
        node = aspen.Tree.FindNode(path)
        if node:
            print(f"[OK] Found: {path}")
            return True
        else:
            print(f"[FAIL] Missing: {path}")
            return False
    except Exception as e:
        print(f"[ERROR] {path}: {e}")
        return False

def inspect():
    try:
        aspen = win32.GetActiveObject("Apwn.Document")
    except:
        print("Could not attach to Aspen. Make sure it is open and the simulation was run with visible=True.")
        return

    print("Verifying loaded state...")
    check_node(aspen, r"\Data\Components\Specifications\Selection")
    check_node(aspen, r"\Data\Properties\Specifications\Global\Selection")
    check_node(aspen, r"\Data\Streams\FEED")
    check_node(aspen, r"\Data\Blocks\B1")

if __name__ == "__main__":
    inspect()
