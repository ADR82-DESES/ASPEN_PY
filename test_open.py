import win32com.client as win32
import os
import time

def main():
    inp_path = os.path.abspath("Methanol_Session_Minimal/temp_simulation.inp")
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitNew() # Get it to a known state
        aspen.Visible = 1
        aspen.SuppressDialogs = 1
        
        print(f"Calling aspen.Open('{inp_path}')...")
        try:
            aspen.Open(inp_path)
            print("Open finished.")
        except Exception as e:
            print(f"Open failed: {e}")
            
        time.sleep(3)
        
        # Verify tree
        node = aspen.Tree.FindNode(r"\Data\Streams")
        if node:
            print(f"Streams node found. Elements: {node.Elements.Count}")
            if node.Elements.Count > 0:
                print("[SUCCESS] Tree populated!")
            else:
                print("[FAIL] Streams node exists but is empty.")
        else:
            print("[FAIL] Streams node not found.")
            
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
