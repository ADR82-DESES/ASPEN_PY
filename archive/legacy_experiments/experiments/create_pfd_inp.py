import win32com.client as win32
import time
import os

def create_pfd():
    print("Connecting to Aspen Plus (Dispatch)...")
    try:
        aspen = win32.Dispatch("Apwn.Document")
        print("Connected. Initializing new simulation...")
        aspen.InitNew()
        print("Initialized. Setting visibility...")
        aspen.Visible = True
        aspen.SuppressDialogs = 1
        
        print("Feeding INP commands via RunScript...")
        # Define components and properties in one go
        # Note: RunScript often expects the script in the same format as an .inp file
        inp_text = """
COMPONENTS
  WATER H2O
SOLIDS
FLOWSHEET
  BLOCK MIXER IN=WATER1 WATER2 OUT=OUT
PROPERTIES IDEAL
BLOCK MIXER MIXER
STREAM WATER1
  SUBSTREAM MIXED TEMP=80 PRES=2 MASS-FLOW=1000
  MASS-FRAC WATER 1
STREAM WATER2
  SUBSTREAM MIXED TEMP=20 PRES=2 MASS-FLOW=1000
  MASS-FRAC WATER 1
"""
        try:
            aspen.RunScript(inp_text)
            print("[OK] RunScript completed")
        except Exception as e:
            print(f"[FAIL] RunScript failed: {e}")
            
        print("Waiting for flowsheet to catch up...")
        time.sleep(5)
        
        print("Checking if MIXER block was created...")
        try:
            mixer = aspen.Tree.FindNode(r"\Data\Blocks\MIXER")
            if mixer:
                print("[SUCCESS] MIXER block found in tree!")
            else:
                print("[FAIL] MIXER block not found in tree.")
        except:
            print("[FAIL] Could not access tree.")

        print("Running simulation...")
        aspen.Engine.Run2()
        
        print("Waiting for results (10s)...")
        time.sleep(10)
        
        try:
            out_temp = aspen.Tree.FindNode(r"\Data\Streams\OUT\Output\TEMP_OUT\MIXED").Value
            print(f"OUT stream temperature: {out_temp} C")
        except:
            print("Could not get results. Check Aspen GUI.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    create_pfd()
