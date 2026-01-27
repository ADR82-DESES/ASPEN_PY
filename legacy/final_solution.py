"""
ASPEN PLUS MIXER SIMULATION - FINAL WORKING VERSION
Based on diagnostic findings: We need to initialize the application first!
"""
import win32com.client as win32
import os
import time
import csv

print("="*70)
print("ASPEN PLUS MIXER SIMULATION - FINAL VERSION")
print("="*70)

# Step 1: Connect
print("\n[1] Connecting to Aspen Plus...")
try:
    aspen = win32.Dispatch("Apwn.Document")
    print("[OK] Connected")
except Exception as e:
    print(f"[FAIL] {e}")
    exit(1)

# Step 2: Initialize - THIS IS THE KEY!
print("\n[2] Initializing Application...")
print("\nThe diagnostic revealed that we must initialize the application.")
print("We have two options:")
print("  A) InitNew - Create a new blank simulation")
print("  B) InitFromArchive2 - Load an existing .bkp file")

choice = input("\nChoose (A/B): ").strip().upper()

if choice == 'A':
    print("\nInitializing new simulation...")
    try:
        # Try InitNew
        aspen.InitNew()
        print("[OK] New simulation initialized")
    except Exception as e:
        print(f"[FAIL] InitNew failed: {e}")
        print("\nTrying alternative: InitFromTemplate2...")
        try:
            # Some versions use templates
            aspen.InitFromTemplate2("MIXERSET.apw")
            print("[OK] Initialized from template")
        except Exception as e2:
            print(f"[FAIL] Template init failed: {e2}")
            print("\nPlease manually create a blank simulation in Aspen Plus:")
            print("1. File -> New -> Blank Simulation")
            print("2. Save it as 'blank.bkp' in this directory")
            print("3. Run this script again and choose option B")
            exit(1)

elif choice == 'B':
    filename = input("\nEnter .bkp filename (or press Enter for 'MixerSimulation.bkp'): ").strip()
    if not filename:
        filename = "MixerSimulation.bkp"
    
    if not os.path.exists(filename):
        print(f"\n[FAIL] File not found: {filename}")
        print("\nPlease create the simulation file first:")
        print("1. Open Aspen Plus")
        print("2. Create a simulation with:")
        print("   - Component: WATER")
        print("   - Property Method: IDEAL")
        print("   - Mixer block: MIXER")
        print("   - Streams: WATER1, WATER2, OUT (connected)")
        print(f"3. Save as '{filename}'")
        print("4. Run this script again")
        exit(1)
    
    print(f"\nLoading {filename}...")
    try:
        full_path = os.path.abspath(filename)
        aspen.InitFromArchive2(full_path)
        print(f"[OK] Loaded: {full_path}")
    except Exception as e:
        print(f"[FAIL] Could not load file: {e}")
        exit(1)

else:
    print("[FAIL] Invalid choice")
    exit(1)

# Step 3: Verify Tree Access
print("\n[3] Verifying Tree Access...")
try:
    tree = aspen.Tree
    data_node = tree.FindNode(r"\Data")
    if data_node:
        print("[OK] Tree is now accessible!")
    else:
        print("[WARN] Tree accessible but \\Data node not found")
except Exception as e:
    print(f"[FAIL] Tree still not accessible: {e}")
    exit(1)

# Step 4: Set Visible
print("\n[4] Making Aspen Plus Visible...")
try:
    aspen.Visible = True
    aspen.SuppressDialogs = 1
    print("[OK] Aspen Plus window is now visible")
except:
    pass

# Step 5: Configure Simulation (if new)
if choice == 'A':
    print("\n[5] Configuring Simulation...")
    
    # Add component
    print("  Adding WATER component...")
    try:
        comp_node = aspen.Tree.FindNode(r"\Data\Components\Specifications\Input\CAG_IDS")
        if comp_node:
            comp_node.Elements.Add("WATER")
            print("  [OK] WATER added")
    except Exception as e:
        print(f"  [WARN] {str(e)[:80]}")
    
    # Set property method
    print("  Setting property method...")
    try:
        method_node = aspen.Tree.FindNode(r"\Data\Properties\Global\Input\METHOD")
        if method_node:
            method_node.Value = "IDEAL"
            print("  [OK] Property method set to IDEAL")
    except Exception as e:
        print(f"  [WARN] {str(e)[:80]}")
    
    # Create streams
    print("  Creating streams...")
    for stream in ["WATER1", "WATER2", "OUT"]:
        try:
            aspen.Tree.FindNode(r"\Data\Streams").Elements.Add(stream)
            print(f"  [OK] Created {stream}")
        except Exception as e:
            print(f"  [WARN] {stream}: {str(e)[:60]}")
    
    # Create mixer
    print("  Creating MIXER block...")
    try:
        aspen.Tree.FindNode(r"\Data\Blocks").Elements.Add("MIXER", "Mixer")
        print("  [OK] MIXER created")
    except Exception as e:
        print(f"  [WARN] {str(e)[:80]}")
    
    print("\n  NOTE: You may need to manually connect streams in the GUI")

# Step 6: Set Inputs
print("\n[6] Setting Input Conditions...")
try:
    # WATER1
    w1 = aspen.Tree.FindNode(r"\Data\Streams\WATER1\Input")
    if w1:
        w1.FindNode(r"TEMP\MIXED").Value = 80.0
        w1.FindNode(r"PRES\MIXED").Value = 2.0
        w1.FindNode(r"TOTFLOW\MIXED").Value = 1000.0
        print("[OK] WATER1: 80°C, 2 bar, 1000 kg/hr")
    
    # WATER2
    w2 = aspen.Tree.FindNode(r"\Data\Streams\WATER2\Input")
    if w2:
        w2.FindNode(r"TEMP\MIXED").Value = 20.0
        w2.FindNode(r"PRES\MIXED").Value = 2.0
        w2.FindNode(r"TOTFLOW\MIXED").Value = 1000.0
        print("[OK] WATER2: 20°C, 2 bar, 1000 kg/hr")
        
except Exception as e:
    print(f"[WARN] Could not set all inputs: {e}")
    print("You may need to set inputs manually in the GUI")

# Step 7: Run Simulation
print("\n[7] Running Simulation...")
run_sim = input("Run simulation now? (y/n): ").strip().lower()

if run_sim == 'y':
    try:
        aspen.Engine.Run2()
        print("[OK] Run command sent")
        print("[WAIT] Waiting 10 seconds for convergence...")
        time.sleep(10)
        
        # Extract results
        print("\n[8] Extracting Results...")
        try:
            out = aspen.Tree.FindNode(r"\Data\Streams\OUT\Output")
            if out:
                temp = out.FindNode(r"TEMP_OUT\MIXED").Value
                pres = out.FindNode(r"PRES_OUT\MIXED").Value
                flow = out.FindNode(r"MASSFLMX\MIXED").Value
                
                print(f"[OK] Temperature: {temp} °C")
                print(f"[OK] Pressure: {pres} bar")
                print(f"[OK] Mass Flow: {flow} kg/hr")
                
                # Save results
                with open("results.csv", 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Parameter", "Value", "Unit"])
                    writer.writerow(["Stream", "OUT", "-"])
                    writer.writerow(["Temperature", temp, "°C"])
                    writer.writerow(["Pressure", pres, "bar"])
                    writer.writerow(["MassFlow", flow, "kg/hr"])
                
                print("\n[OK] Results saved to results.csv")
        except Exception as e:
            print(f"[WARN] Could not extract results: {e}")
            print("Check Aspen Plus GUI for results")
            
    except Exception as e:
        print(f"[FAIL] Simulation error: {e}")
else:
    print("[SKIP] Simulation not run")

print("\n" + "="*70)
print("COMPLETE")
print("="*70)
print("\nCheck the Aspen Plus window to see the flowsheet.")
