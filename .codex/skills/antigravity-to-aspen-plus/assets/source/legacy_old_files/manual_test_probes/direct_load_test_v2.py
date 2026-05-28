"""
RESEARCH: Load and Add Block (Correct Order)
"""
import win32com.client as win32
import os
import time

def test():
    file_path = r"C:\Program Files\AspenTech\Aspen Plus V14.0\Favorites\testprob.bkp"

    print(f"Connecting to Aspen...")
    aspen = win32.Dispatch("Apwn.Document")

    # DO NOT set visible or suppress dialogs yet
    print(f"Loading {file_path}...")
    aspen.InitFromArchive2(os.path.abspath(file_path))

    # NOW set properties
    aspen.Visible = True
    aspen.SuppressDialogs = 1

    print("Waiting 10s for load...")
    time.sleep(10)

    try:
        blocks = aspen.Tree.FindNode(r"\Data\Blocks")
        print(f"Found blocks: {blocks.Elements.Count}")

        # Test addition
        print("Testing Add('B_TEST', 'MIXER')...")
        blocks.Elements.Add("B_TEST", "MIXER")
        print("Successfully added B_TEST!")
    except Exception as e:
        print(f"Error adding block: {e}")

if __name__ == "__main__":
    test()
