import win32com.client as win32
import os
import time

def main():
    root_dir = r"C:\Users\domingueza\ASPEN_PY"
    src_inp = os.path.join(root_dir, "Methanol Plant", "MethanolPlant.inp")
    dst_inp = os.path.join(root_dir, "v14_test.inp")
    
    # Read original
    with open(src_inp, 'r') as f:
        content = f.read()
    
    # Prepend V14 BKP header
    header = 'MM "40.0" FLAVOR "NO" VERSION "40.0" DATETIME "' + time.strftime("%a %b %d %H:%M:%S %Y") + '"\n'
    header += 'MACHINE "WIN-NT/VC"  ; \n'
    
    with open(dst_inp, 'w', newline='\r\n') as f:
        f.write(header + content)
        
    print(f"Created {dst_inp} with V14 header and CRLF.")
    
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitNew()
        aspen.Visible = 1
        aspen.SuppressDialogs = 1
        
        print(f"Importing {dst_inp}...")
        aspen.Import(dst_inp)
        
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
