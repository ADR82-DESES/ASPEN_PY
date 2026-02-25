import os
import sys
import time
import win32com.client as win32

def connect_to_aspen(filepath, visible=True):
    aspen = win32.Dispatch('Apwn.Document') 
    full_path = os.path.abspath(filepath)
    aspen.InitFromArchive2(full_path)
    aspen.Visible = visible
    aspen.SuppressDialogs = 1 
    return aspen

if __name__ == "__main__":
    filepath = r"c:\Users\domingueza\ASPEN_PY\Methanol Plant\MethanolPlant.apw"
    full_path = os.path.abspath(filepath)
    stem = os.path.splitext(os.path.basename(full_path))[0]
    
    print(f"INFO: Connecting to Aspen Plus and opening {filepath}...")
    aspen = connect_to_aspen(filepath, visible=True)
    
    blocks_node = aspen.Tree.FindNode(r"\Data\Blocks")
    if blocks_node is None:
        print("ERROR: NO_BLOCKS — The loaded APW has no blocks (Blocks section missing). Aborting.")
        aspen.Quit()
        sys.exit(1)
        
    print("INFO: Reinitializing simulation...")
    aspen.Reinit()
    
    print("INFO: Running simulation asynchronously...")
    aspen.Engine.Run2(1) # RunAsync
    
    while aspen.Engine.IsRunning:
        time.sleep(1)
        
    print("INFO: Simulation finished.")
    
    try:
        per_error_node = aspen.Tree.FindNode(r"\Data\Results Summary\Run-Status\Output\PER_ERROR")
        if per_error_node is not None:
            val = per_error_node.Value
            if val == 0:
                print("OK: CONVERGED — PER_ERROR = 0")
                output_path = os.path.join(os.path.dirname(full_path), f"{stem}_output.apw")
                try:
                    aspen.SaveAs(output_path)
                    print(f"OK: OUTPUT_SAVED — {output_path}")
                except Exception as save_exc:
                    print(f"ERROR: OUTPUT_SAVE_FAILED — {save_exc}")
                    aspen.Quit()
                    sys.exit(2)
            else:
                print(f"WARNING: NOT_CONVERGED — PER_ERROR = {val}")
                print("WARNING: OUTPUT_NOT_SAVED")
                aspen.Quit()
                sys.exit(3)
        else:
            print("WARNING: STATUS_UNKNOWN")
            print("WARNING: OUTPUT_NOT_SAVED")
            aspen.Quit()
            sys.exit(4)
    except SystemExit:
        raise
    except Exception:
        print("WARNING: STATUS_UNKNOWN")
        print("WARNING: OUTPUT_NOT_SAVED")
        aspen.Quit()
        sys.exit(4)

    print("INFO: Closing Aspen Plus...")
    aspen.Quit()
    print("OK: Done.")
