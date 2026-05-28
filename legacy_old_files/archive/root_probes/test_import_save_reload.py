import win32com.client as win32
import os
import time

def main():
    root_dir = r"C:\Users\domingueza\ASPEN_PY"
    inp_path = os.path.join(root_dir, "Methanol Plant", "MethanolPlant.inp")
    tmp_apw = os.path.join(root_dir, "sync_test.apw")
    
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitNew()
        aspen.Visible = 1
        aspen.SuppressDialogs = 1
        
        print(f"Importing {inp_path}...")
        aspen.Import(inp_path)
        
        print(f"Saving to {tmp_apw}...")
        if os.path.exists(tmp_apw): os.remove(tmp_apw)
        aspen.SaveAs(tmp_apw)
        
        print("Closing and reloading...")
        aspen.Quit()
        
        time.sleep(2)
        
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitFromFile2(tmp_apw)
        aspen.Visible = 1
        
        print("Checking tree...")
        streams = aspen.Tree.FindNode(r"\Data\Streams")
        if streams and streams.Elements.Count > 0:
            print(f"[SUCCESS] Tree populated with {streams.Elements.Count} streams.")
        else:
            print("[FAIL] Tree is still empty or missing.")
            
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
