"""
Rebuild the Methanol Plant simulation from the .inp file.
This script opens Aspen Plus, imports the .inp file, and saves as .bkp.
"""
import os
import sys
import time
import win32com.client as win32

# Configuration
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
INP_FILE = os.path.join(PROJECT_DIR, "MethanolPlant.inp")
BKP_FILE = os.path.join(PROJECT_DIR, "MethanolPlant.bkp")

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def main():
    log("=" * 60)
    log("REBUILDING METHANOL PLANT SIMULATION")
    log("=" * 60)
    
    if not os.path.exists(INP_FILE):
        log(f"ERROR: Input file not found: {INP_FILE}")
        return 1
    
    log(f"Input file: {INP_FILE}")
    
    aspen = None
    try:
        # Try to connect to running instance first
        try:
            aspen = win32.GetActiveObject("Apwn.Document")
            log("Connected to running Aspen Plus instance")
        except:
            log("Starting new Aspen Plus instance...")
            aspen = win32.Dispatch("Apwn.Document")
        
        aspen.Visible = True
        
        try:
            aspen.SuppressDialogs = 1
        except:
            pass
        
        log("Importing .inp file (this will take a moment)...")
        log("Please wait for Aspen Plus to load the flowsheet...")
        
        # Import the .inp file
        # InitFromFile2 reads input files
        aspen.InitFromFile2(INP_FILE)
        
        log("Waiting for import to complete...")
        time.sleep(5)
        
        # Check if streams exist now
        log("Checking if flowsheet was imported...")
        test_stream = aspen.Tree.FindNode(r"\Data\Streams\NG-FEED")
        if test_stream:
            log("[OK] Flowsheet structure detected!")
        else:
            log("[X] Flowsheet not detected - import may have failed")
            log("Please check Aspen Plus window for any error messages.")
            log("")
            log("Manual steps:")
            log("  1. In Aspen Plus, go to File > Import")
            log("  2. Select 'Aspen Plus Input Files (*.inp)'")
            log("  3. Choose MethanolPlant.inp")
            log("  4. Wait for import to complete")
            log("  5. Save as MethanolPlant.bkp")
            return 1
        
        # Save the file
        log(f"Saving as: {BKP_FILE}")
        aspen.SaveAs(BKP_FILE)
        
        time.sleep(2)
        
        if os.path.exists(BKP_FILE):
            size_kb = os.path.getsize(BKP_FILE) / 1024
            log(f"[OK] File saved: {BKP_FILE} ({size_kb:.1f} KB)")
        
        # Now run the simulation
        log("")
        log("=== Running Simulation ===")
        log("Reinitializing...")
        aspen.Reinit()
        
        log("Running simulation...")
        aspen.Run()
        
        # Wait for completion
        max_wait = 300  # 5 minutes
        start_time = time.time()
        while True:
            try:
                if not aspen.EngineRunning:
                    break
            except:
                break
            
            elapsed = time.time() - start_time
            if elapsed > max_wait:
                log("Timeout waiting for simulation")
                break
            
            time.sleep(2)
            if int(elapsed) % 10 == 0:
                log(f"  Running... ({int(elapsed)}s)")
        
        elapsed = time.time() - start_time
        log(f"Simulation completed in {elapsed:.1f} seconds")
        
        # Save again with results
        log("Saving simulation with results...")
        aspen.Save()
        
        log("")
        log("SUCCESS! Simulation is ready.")
        log("Run 'python run_flowsheet.py' to see results.")
        
        return 0
        
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
