"""
RESEARCH: Load and Add Block
"""
import win32com.client as win32
import os
import time

def test():
    file_path = r"C:\Program Files\AspenTech\Aspen Plus V14.0\Favorites\testprob.bkp"

    print(f"Connecting to Aspen...")
    aspen = win32.Dispatch("Apwn.Document")
    aspen.Visible = True
    aspen.SuppressDialogs = 1

    print(f"Loading {file_path}...")
    # Use abspath to be safe
    aspen.InitFromArchive2(os.path.abspath(file_path))

    print("Waiting 10s for load...")
    time.sleep(10)

    print(f"Current Name: {aspen.Name}")

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
