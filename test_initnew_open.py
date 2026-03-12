import win32com.client as win32
import os
import time

def main():
    inp_path = os.path.abspath(r"Methanol Plant\MethanolPlant.inp")
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitNew() # Initialize state
        aspen.Visible = 1
        aspen.SuppressDialogs = 1
        
        print(f"Calling aspen.Open('{inp_path}')...")
        try:
            aspen.Open(inp_path)
            print("Open() called.")
        except Exception as e:
            print(f"Open() failed: {e}")
            
        time.sleep(5)
        
        streams = aspen.Tree.FindNode(r"\Data\Streams")
        if streams and hasattr(streams, "Elements") and streams.Elements.Count > 0:
            print(f"[SUCCESS] Tree populated! Count: {streams.Elements.Count}")
        else:
            print("[FAIL] Tree still empty.")
            
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
