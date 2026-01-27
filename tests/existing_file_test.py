"""
RESEARCH: Adding to Existing File
Loading an example and trying to add a block to it
"""
import win32com.client as win32
import os
import time

def test():
    example_path = r"C:\Program Files\AspenTech\Aspen Plus V14.0\Favorites\testprob.bkp"
    if not os.path.exists(example_path):
        print(f"Example file not found: {example_path}")
        return

    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.Visible = True
        aspen.SuppressDialogs = 1
        
        print(f"Loading example: {example_path}")
        aspen.InitFromArchive2(os.path.abspath(example_path))
        
        print("Waiting for load...")
        time.sleep(15)
        
        blocks = aspen.Tree.FindNode(r"\Data\Blocks")
        if blocks:
            print(f"Found Blocks node with {blocks.Elements.Count} blocks. Testing addition...")
            try:
                # Try adding a mixer
                blocks.Elements.Add("B_NEW_MIX", "MIXER")
                print("  [SUCCESS] Created Mixer B_NEW_MIX")
            except Exception as e:
                print(f"  [FAIL Mixer] {e}")
                
            try:
                # Try adding something else
                blocks.Elements.Add("B_NEW_HEAT", "HEATER")
                print("  [SUCCESS] Created Heater B_NEW_HEAT")
            except Exception as e:
                print(f"  [FAIL Heater] {e}")
        else:
            print("Blocks node NOT found after load.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
