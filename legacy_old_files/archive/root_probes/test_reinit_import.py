import win32com.client as win32
import os
import time

def main():
    inp_path = os.path.abspath(r"Methanol Plant\MethanolPlant.inp")
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitNew()
        aspen.Visible = 1
        aspen.SuppressDialogs = 1
        
        print(f"Importing {inp_path}...")
        aspen.Import(inp_path)
        
        print("Kicking engine with Reinit() and Run2(1)...")
        try:
            aspen.Reinit()
            aspen.Engine.Run2(1) # Async
        except Exception as e:
            print(f"Engine kick failed (as expected if flowsheet not fully built): {e}")
            
        print("Waiting for engine to stop or 10s...")
        start = time.time()
        while aspen.Engine.IsRunning and time.time() - start < 15:
            time.sleep(1)
            
        print("Checking tree...")
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
