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
        
        print("Testing aspen.Application.Import(path)...")
        try:
            aspen.Application.Import(inp_path)
            print("Import called.")
        except Exception as e:
            print(f"aspen.Application.Import failed: {e}")
            
        time.sleep(5)
        
        streams = aspen.Tree.FindNode(r"\Data\Streams")
        if streams and streams.Elements.Count > 0:
            print(f"[SUCCESS] Tree populated via Application.Import. Count: {streams.Elements.Count}")
        else:
             print("Tree still empty. Testing RunCommand('IMPORT ...')...")
             try:
                 # Some versions support direct command execution
                 aspen.ExecuteCommand(f'IMPORT "{inp_path}"')
                 print("ExecuteCommand called.")
             except Exception as e:
                 print(f"ExecuteCommand failed: {e}")
                 
             time.sleep(5)
             streams = aspen.Tree.FindNode(r"\Data\Streams")
             if streams and streams.Elements.Count > 0:
                 print(f"[SUCCESS] Tree populated via ExecuteCommand. Count: {streams.Elements.Count}")
             else:
                 print("[FAIL] Both Application methods failed.")
                 
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
