"""
Aspen Plus Mixer Simulation - Proper Approach
This script creates a mixer simulation by properly initializing Aspen Plus
"""
import win32com.client as win32
import os
import time

print("="*70)
print("ASPEN PLUS MIXER SIMULATION")
print("="*70)

# Configuration
SIMULATION_FILE = "MixerSimulation.bkp"

# Step 1: Connect or Create
print("\n[1] Connecting to Aspen Plus...")
try:
    aspen = win32.Dispatch("Apwn.Document")
    print(f"  [OK] Connected")
    aspen.Visible = True
    aspen.SuppressDialogs = 1
except Exception as e:
    print(f"  [FAIL] Could not connect: {e}")
    exit(1)

# Step 2: Check if we need to create a new simulation
print("\n[2] Checking simulation state...")
try:
    # Try to access the tree - if this fails, we need to initialize
    test_node = aspen.Tree.FindNode(r"\Data")
    if test_node:
        print("  [OK] Simulation document is initialized")
    else:
        print("  [INFO] Document not initialized, needs setup")
except:
    print("  [INFO] Document not initialized, needs setup")

# Step 3: The key insight - we need to tell the user to create a blank simulation manually
print("\n[3] IMPORTANT INSTRUCTIONS:")
print("="*70)
print("The Aspen Plus COM interface requires a simulation to be created")
print("manually first. Please follow these steps:")
print("")
print("IN ASPEN PLUS:")
print("1. Click 'File' -> 'New'")
print("2. Select 'Blank Simulation'")
print("3. Click 'OK'")
print("4. In the 'Setup' -> 'Components' -> 'Specifications':")
print("   - Click 'Component ID' field")
print("   - Type 'WATER' and press Enter")
print("   - Aspen will auto-fill it as H2O")
print("5. Go to 'Setup' -> 'Properties' -> 'Specifications':")
print("   - Select 'IDEAL' as the Base method")
print("6. Click 'Next' until you reach the main flowsheet")
print("7. From the Model Palette, drag a 'Mixer' onto the flowsheet")
print("8. Name it 'MIXER'")
print("9. Create 3 material streams:")
print("   - WATER1 (inlet to MIXER)")
print("   - WATER2 (inlet to MIXER)")  
print("   - OUT (outlet from MIXER)")
print("10. Connect them to the MIXER")
print("11. Save the file as 'MixerSimulation.bkp' in this directory:")
print(f"    {os.getcwd()}")
print("")
print("THEN run this script again, and it will:")
print("- Set the input conditions")
print("- Run the simulation")
print("- Extract and save the results")
print("="*70)

# Check if the file exists
if os.path.exists(SIMULATION_FILE):
    print(f"\n[4] Found {SIMULATION_FILE}!")
    print("  Loading simulation...")
    
    try:
        full_path = os.path.abspath(SIMULATION_FILE)
        aspen.InitFromArchive2(full_path)
        print(f"  [OK] Loaded: {full_path}")
        
        # Now set inputs
        print("\n[5] Setting Input Conditions...")
        
        # WATER1
        try:
            w1_input = aspen.Tree.FindNode(r"\Data\Streams\WATER1\Input")
            w1_input.FindNode(r"TEMP\MIXED").Value = 80.0
            w1_input.FindNode(r"PRES\MIXED").Value = 2.0
            w1_input.FindNode(r"TOTFLOW\MIXED").Value = 1000.0
            w1_input.FindNode(r"FRAC\MIXED\WATER").Value = 1.0
            print("  [OK] WATER1: 80C, 2bar, 1000kg/hr")
        except Exception as e:
            print(f"  [ERROR] WATER1: {e}")
        
        # WATER2
        try:
            w2_input = aspen.Tree.FindNode(r"\Data\Streams\WATER2\Input")
            w2_input.FindNode(r"TEMP\MIXED").Value = 20.0
            w2_input.FindNode(r"PRES\MIXED").Value = 2.0
            w2_input.FindNode(r"TOTFLOW\MIXED").Value = 1000.0
            w2_input.FindNode(r"FRAC\MIXED\WATER").Value = 1.0
            print("  [OK] WATER2: 20C, 2bar, 1000kg/hr")
        except Exception as e:
            print(f"  [ERROR] WATER2: {e}")
        
        # Run simulation
        print("\n[6] Running Simulation...")
        aspen.Engine.Run2()
        print("  [OK] Run command sent")
        print("  [WAIT] Waiting for convergence...")
        time.sleep(10)
        
        # Extract results
        print("\n[7] Extracting Results...")
        try:
            out_output = aspen.Tree.FindNode(r"\Data\Streams\OUT\Output")
            
            temp = out_output.FindNode(r"TEMP_OUT\MIXED").Value
            pres = out_output.FindNode(r"PRES_OUT\MIXED").Value
            flow = out_output.FindNode(r"MASSFLMX\MIXED").Value
            
            print(f"  [OK] Temperature: {temp} C")
            print(f"  [OK] Pressure: {pres} bar")
            print(f"  [OK] Mass Flow: {flow} kg/hr")
            
            # Save to CSV
            import csv
            with open("results.csv", 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Parameter", "Value", "Unit"])
                writer.writerow(["Stream", "OUT", "-"])
                writer.writerow(["Temperature", temp, "C"])
                writer.writerow(["Pressure", pres, "bar"])
                writer.writerow(["MassFlow", flow, "kg/hr"])
            
            print("\n  [OK] Results saved to results.csv")
            
        except Exception as e:
            print(f"  [ERROR] Could not extract results: {e}")
        
    except Exception as e:
        print(f"  [ERROR] Could not load simulation: {e}")
else:
    print(f"\n[4] File '{SIMULATION_FILE}' not found.")
    print("  Please follow the instructions above to create it manually.")

print("\n" + "="*70)
print("DONE")
print("="*70)
