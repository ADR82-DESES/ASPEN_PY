import os
import sys
import win32com.client as win32
import time

# Configuration
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
FILENAME = "MethanolPlant.bkp"
FULL_PATH = os.path.join(PROJECT_DIR, FILENAME)

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def load_constraints():
    constraints = {}
    c_file = os.path.join(PROJECT_DIR, "constraints.txt")
    if os.path.exists(c_file):
        with open(c_file, 'r') as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    key, val = line.split("=", 1)
                    constraints[key.strip()] = float(val.split("#")[0].strip())
    return constraints

def connect_aspen():
    log("Initializing Aspen Plus Interface...")
    aspen = None
    
    # First, try to connect to an already running instance
    try:
        log("Checking for running Aspen Plus instance...")
        aspen = win32.GetActiveObject("Apwn.Document")
        log("Connected to running Aspen Plus instance!")
        aspen.SuppressDialogs = 1
        return aspen
    except:
        log("No running instance found, will open simulation file...")
    
    # Fall back to opening the simulation file
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.SuppressDialogs = 1
        
        if os.path.exists(FULL_PATH):
            log(f"Found existing simulation file: {FILENAME}")
            log("Opening simulation...")
            aspen.InitFromArchive2(FULL_PATH)
        else:
            log(f"Warning: {FILENAME} not found in {PROJECT_DIR}")
            log("Creating new blank simulation instance...")
            aspen.Visible = True
            log("Please create a new simulation and save it as 'MethanolPlant.bkp' in this folder.")
            
        aspen.Visible = True
        return aspen
    except Exception as e:
        log(f"Error connecting to Aspen Plus: {e}")
        return None

def main():
    log("=== Methanol Plant Automation Setup ===")
    
    # 1. Load Constraints
    constraints = load_constraints()
    log(f"Loaded {len(constraints)} constraints.")
    for k, v in constraints.items():
        log(f"  - {k}: {v}")

    # 2. Connect to Aspen
    aspen = connect_aspen()
    if not aspen:
        return

    # 3. Basic Validation of Environment
    log("Aspen Plus is running.")
    
    # Check if simulation is loaded
    try:
        # Try to access main tree to verify load
        node = aspen.Tree.FindNode(r"\Data\Setup")
        if node:
            log("Simulation Tree is accessible.")
        else:
            log("Simulation Tree not ready (New file?).")
    except:
        log("waiting for user interaction...")

    log("Setup Complete. You can now build the PFD based on DESIGN_BASIS.md")

if __name__ == "__main__":
    main()
