import os
import subprocess
import time
import win32com.client as win32

# Configuration
ASPEN_EXE = r"C:\Program Files\AspenTech\Aspen Plus V14.0\GUI\Xeq\aspenplus.exe"
INP_FILE = "AutomatedMixer.inp"
BKP_FILE = "AutomatedMixer.bkp"

# 1. Create the INP file
inp_content = """COMPONENTS
  WATER H2O
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

with open(INP_FILE, "w") as f:
    f.write(inp_content)

print(f"Created {INP_FILE}")

# 2. Run Aspen Plus with the INP file
# The command line for Aspen Plus usually accepts the INP file as an argument
# Adding /RUN or /B (batch) or just the file
print(f"Starting Aspen Plus with {INP_FILE}...")
try:
    # We use subprocess.Popen to let it run
    # Aspen often takes a while to initialize from INP
    proc = subprocess.Popen([ASPEN_EXE, os.path.abspath(INP_FILE)])
    print("Aspen Plus process started. Waiting for it to create the flowsheet...")
    
    # Wait for the process to at least start up
    time.sleep(30)
    
    # Now try to connect via COM to "save as" BKP
    print("Attempting to connect via COM to save the backup file...")
    aspen = None
    for _ in range(10):
        try:
            aspen = win32.GetActiveObject("Apwn.Document")
            if aspen: break
        except:
            time.sleep(5)
            
    if aspen:
        print("Connected! Saving as .bkp...")
        aspen.SaveAs(os.path.abspath(BKP_FILE))
        print(f"[SUCCESS] Flowsheet created and saved to {BKP_FILE}")
        aspen.Visible = True
    else:
        print("[WARN] Could not connect via COM. You may need to manually save the opened Aspen Plus window.")

except Exception as e:
    print(f"Error: {e}")
