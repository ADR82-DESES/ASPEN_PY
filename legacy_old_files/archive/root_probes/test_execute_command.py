import win32com.client as win32
import os
import time

def main():
    inp_path = os.path.abspath("Methanol_Session_Minimal/temp_simulation.inp")
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitNew()
        aspen.Visible = 1
        aspen.SuppressDialogs = 1
        
        print(f"Calling ExecuteCommand('IMPORT \"{inp_path}\"')...")
        try:
            aspen.ExecuteCommand(f"IMPORT \"{inp_path}\"")
            print("ExecuteCommand finished.")
        except Exception as e:
            print(f"ExecuteCommand failed: {e}")
            
        time.sleep(2)
        
        # Verify tree
        node = aspen.Tree.FindNode(r"\Data\Streams")
        if node and node.Elements.Count > 0:
            print(f"[SUCCESS] Tree populated with {node.Elements.Count} streams.")
        else:
            print("[FAIL] Tree is empty.")
            
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
