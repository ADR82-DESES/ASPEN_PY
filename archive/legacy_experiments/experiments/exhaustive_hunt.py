"""
Final attempt at Block Creation using varied model strings
"""
import win32com.client as win32
import os
import time

def test_creation():
    aspen = win32.Dispatch("Apwn.Document")
    # Instead of InitNew, we'll try to use a dummy file if InitNew hangs
    try:
        print("Initializing New Simulation...")
        aspen.InitNew()
        time.sleep(10) # Give it time
    except:
        print("InitNew failed or timed out")
        return

    aspen.Visible = True
    aspen.SuppressDialogs = 1

    blocks = aspen.Tree.FindNode(r"\Data\Blocks")
    
    # These are some observed internal strings for models
    test_types = [
        "MIXER", "Mixer", "Mixers", 
        "FLASH2", "Flash2",
        "HEATER", "Heater",
        "RADFRAC", "RadFrac",
        "V-DRUM1", "v-drum1"
    ]

    print("\nStarting exhaustive block type hunt...")
    for t in test_types:
        print(f"Trying: {t}")
        try:
            blocks.Elements.Add("B_" + t.replace("-","_"), t)
            print(f"  [SUCCESS!!!] Created block with type: {t}")
        except Exception as e:
            # print(f"  [FAIL] {str(e)[:50]}")
            pass

    # One more trick: Many COM objects have an 'ActiveDocument' or similar
    # But for Aspen, maybe we can use the 'Application' object directly
    try:
        app = aspen.Application
        # Look for unit op creation methods on app
        for attr in dir(app):
            if "Create" in attr or "Add" in attr:
                print(f"Interesting App Method: {attr}")
    except:
        pass

if __name__ == "__main__":
    test_creation()
