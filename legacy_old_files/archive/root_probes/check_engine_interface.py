import win32com.client as win32
import os

def main():
    try:
        aspen = win32.GetActiveObject("Apwn.Document")
    except:
        aspen = win32.Dispatch("Apwn.Document")
    
    aspen.InitNew()
    aspen.Visible = 1
    
    print("Checking for EngineInterface...")
    if hasattr(aspen, "EngineInterface"):
         print("[OK] Found EngineInterface")
         try:
             # We try a simple command
             # aspen.EngineInterface.RunCommand("IMPORT ...")? 
             # Let's see if we can call it.
             print("Methods on EngineInterface are often not visible to hasattr. Trying direct call.")
             # No, better just check members.
         except:
             pass
    else:
        print("[FAIL] EngineInterface missing")

if __name__ == "__main__":
    main()
