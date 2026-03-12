import win32com.client as win32
import os
import time

def main():
    apw_path = os.path.abspath(r"Methanol Plant\MethanolPlant_ready.apw")
    if not os.path.exists(apw_path):
        print(f"APW missing at {apw_path}")
        return

    try:
        aspen = win32.Dispatch("Apwn.Document")
        # InitFromArchive2 is standard for modern .bkp/.apw
        print(f"Initializing from archive: {apw_path}")
        aspen.InitFromArchive2(apw_path)
        aspen.Visible = 1
        aspen.SuppressDialogs = 1
        
        print("Starting simulation run...")
        aspen.Reinit()
        aspen.Engine.Run2(1) # Async
        
        start_time = time.time()
        while aspen.Engine.IsRunning:
            if time.time() - start_time > 30:
                print("Simulation timeout (30s)")
                aspen.Engine.Stop()
                break
            time.sleep(1)
            
        print(f"Simulation finished in {time.time() - start_time:.2f}s")
        
        # Check status
        try:
            per_error = aspen.Tree.FindNode(r"\Data\Results Summary\Run-Status\Output\PER_ERROR").Value
            print(f"PER_ERROR: {per_error}")
        except:
            print("Could not find PER_ERROR node.")
            
        # aspen.Quit()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
