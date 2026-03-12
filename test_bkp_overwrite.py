import win32com.client as win32
import os
import time

def main():
    bkp_path = os.path.abspath(r"Methanol Plant\MethanolPlant.bkp")
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitFromArchive2(bkp_path)
        aspen.Visible = 1
        aspen.SuppressDialogs = 1
        
        print(f"BKP Loaded: {bkp_path}")
        
        # Test overwriting a value in NG-FEED (already exists in the BKP)
        temp_node = aspen.Tree.FindNode(r"\Data\Streams\NG-FEED\Input\TEMP\MIXED")
        if temp_node:
            print(f"Current NG-FEED Temp: {temp_node.Value}")
            temp_node.Value = 45.0
            print(f"New NG-FEED Temp: {temp_node.Value}")
            
            print("Running simulation...")
            aspen.Reinit()
            aspen.Run2(1) # Sync or Async depending on version, run_flowsheet uses Run()
            
            # Wait
            start = time.time()
            while aspen.EngineRunning and time.time() - start < 30:
                time.sleep(1)
            
            print("Run finished. Checking results...")
            res_node = aspen.Tree.FindNode(r"\Data\Streams\NG-FEED\Output\TEMP_OUT\MIXED")
            if res_node:
                print(f"Resulting NG-FEED Temp: {res_node.Value}")
                print("[SUCCESS] BKP Template Overwrite strategy works!")
            else:
                print("[WARNING] Result node not found (converged?).")
        else:
            print("[FAIL] Could not find NG-FEED Temp node.")
            
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
