"""
Script to create the MethanolPlant.bkp file from MethanolPlant.inp
Launches Aspen Plus V14.0 with the input file.
"""
import os
import sys
import time
import subprocess

# Configuration
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
INP_FILE = os.path.join(PROJECT_DIR, "MethanolPlant.inp")
BKP_FILE = os.path.join(PROJECT_DIR, "MethanolPlant.bkp")

# Aspen Plus V14.0 executable path
ASPEN_EXE = r"C:\Program Files\AspenTech\Aspen Plus V14.0\GUI\Xeq\AspenPlus.exe"

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def main():
    log("=== Creating MethanolPlant.bkp from .inp file ===")
    log("")
    
    if not os.path.exists(INP_FILE):
        log(f"ERROR: Input file not found: {INP_FILE}")
        return 1
    
    if not os.path.exists(ASPEN_EXE):
        log(f"ERROR: Aspen Plus not found at: {ASPEN_EXE}")
        return 1
    
    log(f"Input file: {INP_FILE}")
    log(f"Aspen Plus: {ASPEN_EXE}")
    log("")
    
    try:
        # Launch Aspen Plus with the input file
        log("Launching Aspen Plus with the input file...")
        process = subprocess.Popen([ASPEN_EXE, INP_FILE])
        log(f"Aspen Plus launched (PID: {process.pid})")
        log("")
        log("=" * 60)
        log("IMPORTANT: Aspen Plus is now opening.")
        log("")
        log("The simulation will be imported from MethanolPlant.inp.")
        log("Please wait for the import to complete, then:")
        log("")
        log("  1. Wait for the flowsheet to fully load")
        log("  2. Go to File > Save As")
        log(f"  3. Save as 'MethanolPlant.bkp' in:")
        log(f"     {PROJECT_DIR}")
        log("")
        log("After saving, run: python automation_setup.py")
        log("=" * 60)
        
        # Wait for the file to be created
        log("")
        log("Waiting for MethanolPlant.bkp to be created...")
        log("(This script will detect when you save the file)")
        log("")
        
        wait_count = 0
        max_wait = 600  # 10 minutes max
        
        while wait_count < max_wait:
            if os.path.exists(BKP_FILE):
                size_kb = os.path.getsize(BKP_FILE) / 1024
                log(f"SUCCESS! MethanolPlant.bkp detected ({size_kb:.1f} KB)")
                log("")
                log("You can now run: python automation_setup.py")
                return 0
            
            time.sleep(5)
            wait_count += 5
            
            if wait_count % 30 == 0:
                log(f"  Still waiting... ({wait_count}s elapsed)")
        
        log("Timeout waiting for file. Please save manually.")
        return 1
        
    except Exception as e:
        log(f"ERROR: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
