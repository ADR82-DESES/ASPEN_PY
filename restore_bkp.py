import win32com.client as win32
import os
import time

def main():
    root_dir = r"C:\Users\domingueza\ASPEN_PY"
    inp_path = os.path.join(root_dir, "Methanol Plant", "MethanolPlant.inp")
    out_apw = os.path.join(root_dir, "Methanol Plant", "MethanolPlant_restored.apw")
    
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitNew()
        aspen.Visible = 1
        aspen.SuppressDialogs = 0 # LET THE USER SEE PROBLEMS
        
        print(f"Importing {inp_path}...")
        aspen.Import(inp_path)
        
        print("Waiting 15s for GUI to settle...")
        time.sleep(15)
        
        print("Checking tree...")
        streams = aspen.Tree.FindNode(r"\Data\Streams")
        if streams and hasattr(streams, "Elements") and streams.Elements.Count > 0:
            print(f"[SUCCESS] Tree populated! Count: {streams.Elements.Count}. Saving to {out_apw}...")
            if os.path.exists(out_apw): os.remove(out_apw)
            aspen.SaveAs(out_apw)
        else:
            print("[FAIL] Tree still empty after Manual-style Import.")
            
        # Do not quit, let the user see it
        # aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
