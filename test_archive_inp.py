import win32com.client as win32
import os
import time

def main():
    inp_path = os.path.abspath(r"Methanol Plant\MethanolPlant.inp")
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.SuppressDialogs = 1
        print(f"Calling InitFromArchive2('{inp_path}')...")
        aspen.InitFromArchive2(inp_path)
        print("InitFromArchive2 finished.")
        
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
