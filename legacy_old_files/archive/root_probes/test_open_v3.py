import win32com.client as win32
import os
import time

def main():
    inp_path = os.path.abspath(r"Methanol Plant\MethanolPlant.inp")
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.Visible = 1
        aspen.SuppressDialogs = 1
        
        print(f"Calling aspen.Open('{inp_path}')...")
        aspen.Open(inp_path)
        print("Open() finished.")
        
        time.sleep(5)
        
        root = aspen.Tree.FindNode(r"\Data")
        if root:
            print(f"Tree found. Elements under \Data: {root.Elements.Count}")
            streams = aspen.Tree.FindNode(r"\Data\Streams")
            if streams:
                print(f"Streams count: {streams.Elements.Count}")
            else:
                print("Streams node not found.")
        else:
            print("Tree NOT found.")
            
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
