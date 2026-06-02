import win32com.client as win32
import os
import time

def main():
    inp_path = os.path.abspath(r"Methanol Plant\MethanolPlant.inp")
    if not os.path.exists(inp_path):
        print(f"Manual INP missing at {inp_path}")
        return

    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitNew()
        aspen.Visible = 1
        aspen.SuppressDialogs = 1
        
        print(f"Importing manual script: {inp_path}")
        # Type 4 for .inp
        aspen.Import(inp_path)
        time.sleep(3)
        
        streams_node = aspen.Tree.FindNode(r"\Data\Streams")
        if streams_node:
            count = streams_node.Elements.Count
            print(f"Streams found: {count}")
            if count > 0:
                print("[SUCCESS] Manual INP populated the tree!")
            else:
                print("[FAIL] Manual INP tree is empty.")
        else:
            print("[FAIL] Streams node not found.")
            
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
