"""
RESEARCH: Testing AddChild and other IHNode methods
"""
import win32com.client as win32
import time

def test_addchild():
    try:
        aspen = win32.Dispatch("Apwn.Document")
        # Try to use whatever is open or start new
        try:
             aspen.InitNew()
             time.sleep(5)
        except:
             pass

        aspen.SuppressDialogs = 1

        blocks = aspen.Tree.FindNode(r"\Data\Blocks")
        if not blocks:
             print("Blocks node not found")
             return

        print("Testing AddChild('B_CHILD', 'MIXER')...")
        try:
             # AddChild(Name, child)
             res = blocks.AddChild("B_CHILD", "MIXER")
             print(f"  [SUCCESS] AddChild result: {res}")
        except Exception as e:
             print(f"  [FAIL] AddChild: {e}")

        print("\nTesting NewChild('B_NEW')...")
        try:
             res = blocks.NewChild("B_NEW")
             print(f"  [SUCCESS] NewChild result: {res}")
             # If created, we have to set the model type
             b_node = aspen.Tree.FindNode(r"\Data\Blocks\B_NEW")
             if b_node:
                  try:
                       b_node.Value = "MIXER"
                       print("  Successfully set B_NEW.Value = 'MIXER'")
                  except Exception as e:
                       print(f"  Failed set Value: {e}")
        except Exception as e:
             print(f"  [FAIL] NewChild: {e}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_addchild()
