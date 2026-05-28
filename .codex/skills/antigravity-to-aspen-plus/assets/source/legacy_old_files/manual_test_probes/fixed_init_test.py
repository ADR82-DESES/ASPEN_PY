"""
RESEARCH: Corrected Init Sequence
Setting SuppressDialogs BEFORE InitNew
"""
import win32com.client as win32
import time

def test():
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.Visible = True
        aspen.SuppressDialogs = 1 # Set this ASAP

        print("Initializing New Simulation (with dialogs suppressed)...")
        aspen.InitNew()

        # Give it a lot of time
        for i in range(20):
            time.sleep(1)
            print(f"Waiting... {i+1}s")

        blocks = aspen.Tree.FindNode(r"\Data\Blocks")
        if blocks:
            print("Found Blocks node. Testing simple creation...")
            try:
                blocks.Elements.Add("B1", "MIXER")
                print("  [SUCCESS] Created B1")
            except Exception as e:
                print(f"  [FAIL] {e}")
        else:
            print("Blocks node NOT found.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
