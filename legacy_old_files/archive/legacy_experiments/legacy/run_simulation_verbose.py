import win32com.client as win32
import sys

print("=" * 70)
print("ASPEN PLUS MIXER SIMULATION - VERBOSE MODE")
print("=" * 70)

# Step 1: Connect
print("\n[STEP 1] Connecting to Aspen Plus...")
aspen = None
try:
    aspen = win32.Dispatch("Apwn.Document")
    print(f"  [OK] Connected: {aspen.Name}")
    aspen.Visible = True
    aspen.SuppressDialogs = 1
except Exception as e:
    print(f"  [FAIL] Connection failed: {e}")
    sys.exit(1)

# Step 2: Define Components
print("\n[STEP 2] Defining Components...")
try:
    base_path = r"\Data\Components\Specifications\Input"
    input_node = aspen.Tree.FindNode(base_path)
    
    if input_node:
        print(f"  [OK] Found components input node")
        
        # Add component
        cag_ids = input_node.FindNode("CAG_IDS")
        if cag_ids:
            try:
                cag_ids.Elements.Add("WATER")
                print(f"  [OK] Added component: WATER")
            except:
                print(f"  [INFO] Component WATER already exists")
        
        # Set alias
        try:
            aspen.Tree.FindNode(base_path + r"\CAG_ALIAS\WATER").Value = "H2O"
            aspen.Tree.FindNode(base_path + r"\CAG_NAME\WATER").Value = "Water"
            print(f"  [OK] Set alias: H2O")
        except Exception as e:
            print(f"  [WARN] Warning setting alias: {e}")
    else:
        print(f"  [FAIL] Components input node not found")
except Exception as e:
    print(f"  [FAIL] Error: {e}")

# Step 3: Set Property Method
print("\n[STEP 3] Setting Property Method...")
try:
    path_global = r"\Data\Properties\Global\Input\METHOD"
    node = aspen.Tree.FindNode(path_global)
    if node:
        node.Value = "IDEAL"
        print(f"  [OK] Set property method: IDEAL")
    else:
        print(f"  [WARN] Method node not found")
except Exception as e:
    print(f"  [FAIL] Error: {e}")

# Step 4: Create Flowsheet
print("\n[STEP 4] Creating Flowsheet...")
try:
    # Add mixer block
    blocks = aspen.Tree.FindNode(r"\Data\Blocks")
    try:
        blocks.Elements.Add("MIXER", "Mixer")
        print(f"  [OK] Added MIXER block")
    except:
        print(f"  [INFO] MIXER block already exists")
    
    # Add streams
    streams = aspen.Tree.FindNode(r"\Data\Streams")
    for stream_name in ["WATER1", "WATER2", "OUT"]:
        try:
            streams.Elements.Add(stream_name, "MATERIAL")
            print(f"  [OK] Added stream: {stream_name}")
        except:
            print(f"  [INFO] Stream {stream_name} already exists")
    
    # Connect streams to mixer
    mixer = blocks.Elements.Item("MIXER")
    
    # Input feeds
    feed = mixer.FindNode(r"Input\FEED")
    for s in ["WATER1", "WATER2"]:
        try:
            feed.Elements.Add(s)
            print(f"  [OK] Connected {s} to MIXER input")
        except:
            print(f"  [INFO] {s} already connected")
    
    # Output product
    prod = mixer.FindNode(r"Output\PROD")
    try:
        prod.Elements.Add("OUT")
        print(f"  [OK] Connected OUT to MIXER output")
    except:
        print(f"  [INFO] OUT already connected")
        
except Exception as e:
    print(f"  [FAIL] Error: {e}")

# Step 5: Set Input Conditions
print("\n[STEP 5] Setting Input Conditions...")
try:
    streams = aspen.Tree.FindNode(r"\Data\Streams")
    
    # WATER1: 80C, 2 bar, 1000 kg/hr
    print("  Setting WATER1...")
    st1 = streams.Elements.Item("WATER1")
    inp1 = st1.FindNode("Input")
    inp1.FindNode(r"TEMP\MIXED").Value = 80.0
    inp1.FindNode(r"PRES\MIXED").Value = 2.0
    inp1.FindNode(r"TOTFLOW\MIXED").Value = 1000.0
    frac1 = inp1.FindNode(r"FRAC\MIXED")
    frac1.Elements.Item("WATER").Value = 1.0
    print(f"    [OK] T=80C, P=2bar, F=1000kg/hr, 100% Water")
    
    # WATER2: 20C, 2 bar, 1000 kg/hr
    print("  Setting WATER2...")
    st2 = streams.Elements.Item("WATER2")
    inp2 = st2.FindNode("Input")
    inp2.FindNode(r"TEMP\MIXED").Value = 20.0
    inp2.FindNode(r"PRES\MIXED").Value = 2.0
    inp2.FindNode(r"TOTFLOW\MIXED").Value = 1000.0
    frac2 = inp2.FindNode(r"FRAC\MIXED")
    frac2.Elements.Item("WATER").Value = 1.0
    print(f"    [OK] T=20C, P=2bar, F=1000kg/hr, 100% Water")
    
except Exception as e:
    print(f"  [FAIL] Error: {e}")

# Step 6: Run Simulation
print("\n[STEP 6] Running Simulation...")
try:
    aspen.Engine.Run2()
    print(f"  [OK] Simulation run command sent")
    print(f"  [WAIT] Waiting for convergence...")
    
    # Wait a bit for simulation to complete
    import time
    time.sleep(5)
    
except Exception as e:
    print(f"  [FAIL] Error: {e}")

# Step 7: Extract Results
print("\n[STEP 7] Extracting Results...")
try:
    out_base = r"\Data\Streams\OUT\Output"
    
    # Try different path variations
    paths_to_try = {
        "Temperature": [r"\TEMP_OUT\MIXED", r"\TEMP\MIXED", r"\TEMP"],
        "Pressure": [r"\PRES_OUT\MIXED", r"\PRES\MIXED", r"\PRES"],
        "MassFlow": [r"\TOTFLOW_OUT\MIXED", r"\MASSFLOW\MIXED", r"\TOTFLOW"]
    }
    
    results = {}
    for param, path_list in paths_to_try.items():
        found = False
        for path in path_list:
            try:
                node = aspen.Tree.FindNode(out_base + path)
                if node and node.Value is not None:
                    results[param] = node.Value
                    print(f"  [OK] {param}: {node.Value} (from {path})")
                    found = True
                    break
            except:
                pass
        if not found:
            results[param] = "N/A"
            print(f"  [FAIL] {param}: Could not retrieve")
    
    # Save to CSV
    import csv
    with open("results.csv", 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Parameter", "Value", "Unit"])
        writer.writerow(["Stream", "OUT", "-"])
        writer.writerow(["Temperature", results["Temperature"], "C"])
        writer.writerow(["Pressure", results["Pressure"], "bar"])
        writer.writerow(["MassFlow", results["MassFlow"], "kg/hr"])
    
    print(f"\n  [OK] Results saved to results.csv")
    
except Exception as e:
    print(f"  [FAIL] Error: {e}")

print("\n" + "=" * 70)
print("SIMULATION COMPLETE")
print("=" * 70)
print("\nCheck results.csv for output data")
print("Check Aspen Plus window for flowsheet visualization")
