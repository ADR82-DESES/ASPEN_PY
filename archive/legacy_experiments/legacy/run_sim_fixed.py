import win32com.client as win32
import time

print("="*70)
print("ASPEN PLUS MIXER SIMULATION - FIXED VERSION")
print("="*70)

# Step 1: Connect
print("\n[1] Connecting to Aspen Plus...")
try:
    aspen = win32.Dispatch("Apwn.Document")
    print(f"  [OK] Connected: {aspen.Name}")
    aspen.Visible = True
    aspen.SuppressDialogs = 1
except Exception as e:
    print(f"  [FAIL] {e}")
    exit(1)

# Step 2: Initialize a new simulation (important!)
print("\n[2] Initializing new simulation...")
try:
    # This ensures we start fresh
    aspen.InitFromTemplate2("MIXERSET.apw")
    print("  [OK] Initialized from template")
except Exception as e:
    print(f"  [INFO] Could not init from template: {e}")
    print("  [INFO] Continuing with existing document...")

# Step 3: Define Components
print("\n[3] Defining Components...")
try:
    # Navigate to components
    comp_ids = aspen.Tree.FindNode(r"\Data\Components\Specifications\Input\CAG_IDS")
    
    if comp_ids:
        # Clear existing and add WATER
        try:
            comp_ids.Elements.Add("WATER")
            print("  [OK] Added WATER component")
        except Exception as e:
            print(f"  [INFO] WATER may already exist: {e}")
        
        # Set component type to conventional
        try:
            comp_type = aspen.Tree.FindNode(r"\Data\Components\Specifications\Input\COMPTYPE")
            if comp_type:
                comp_type.Value = "CONV"
                print("  [OK] Set component type to CONVENTIONAL")
        except Exception as e:
            print(f"  [WARN] Could not set component type: {e}")
            
    else:
        print("  [FAIL] Could not find components node")
        
except Exception as e:
    print(f"  [ERROR] {e}")

# Step 4: Set Property Method
print("\n[4] Setting Property Method...")
try:
    # Set global property method
    method_node = aspen.Tree.FindNode(r"\Data\Properties\Global\Input\METHOD")
    if method_node:
        method_node.Value = "IDEAL"
        print("  [OK] Set property method to IDEAL")
    else:
        print("  [WARN] Could not find METHOD node")
except Exception as e:
    print(f"  [ERROR] {e}")

# Step 5: Create Streams FIRST (before blocks)
print("\n[5] Creating Streams...")
try:
    streams_node = aspen.Tree.FindNode(r"\Data\Streams")
    
    if streams_node:
        for stream_name in ["WATER1", "WATER2", "OUT"]:
            try:
                # Check if exists
                existing = streams_node.FindNode(stream_name)
                if not existing:
                    streams_node.Elements.Add(stream_name)
                    print(f"  [OK] Created stream: {stream_name}")
                else:
                    print(f"  [INFO] Stream {stream_name} already exists")
            except Exception as e:
                print(f"  [WARN] Issue with {stream_name}: {e}")
    else:
        print("  [FAIL] Could not find Streams node")
        
except Exception as e:
    print(f"  [ERROR] {e}")

# Step 6: Create Mixer Block
print("\n[6] Creating Mixer Block...")
try:
    blocks_node = aspen.Tree.FindNode(r"\Data\Blocks")
    
    if blocks_node:
        try:
            # Check if exists
            existing = blocks_node.FindNode("MIXER")
            if not existing:
                blocks_node.Elements.Add("MIXER")
                print("  [OK] Created MIXER block")
                
                # Set block type
                mixer_node = blocks_node.FindNode("MIXER")
                if mixer_node:
                    input_node = mixer_node.FindNode("Input")
                    if input_node:
                        type_node = input_node.FindNode("TYPE")
                        if type_node:
                            type_node.Value = "Mixer"
                            print("  [OK] Set MIXER type")
            else:
                print("  [INFO] MIXER already exists")
        except Exception as e:
            print(f"  [WARN] Issue creating MIXER: {e}")
    else:
        print("  [FAIL] Could not find Blocks node")
        
except Exception as e:
    print(f"  [ERROR] {e}")

# Step 7: Connect Streams to Mixer
print("\n[7] Connecting Streams to Mixer...")
try:
    mixer_node = aspen.Tree.FindNode(r"\Data\Blocks\MIXER")
    
    if mixer_node:
        # Connect inlet streams
        feed_node = mixer_node.FindNode(r"Ports\F(IN)")
        if feed_node:
            for stream in ["WATER1", "WATER2"]:
                try:
                    feed_node.Elements.Add(stream)
                    print(f"  [OK] Connected {stream} to MIXER inlet")
                except Exception as e:
                    print(f"  [INFO] {stream} connection: {e}")
        else:
            print("  [WARN] Could not find inlet port")
        
        # Connect outlet stream
        prod_node = mixer_node.FindNode(r"Ports\P(OUT)")
        if prod_node:
            try:
                prod_node.Elements.Add("OUT")
                print("  [OK] Connected OUT to MIXER outlet")
            except Exception as e:
                print(f"  [INFO] OUT connection: {e}")
        else:
            print("  [WARN] Could not find outlet port")
    else:
        print("  [FAIL] Could not find MIXER block")
        
except Exception as e:
    print(f"  [ERROR] {e}")

# Step 8: Set Stream Inputs
print("\n[8] Setting Stream Inputs...")
try:
    # WATER1: Hot water
    water1 = aspen.Tree.FindNode(r"\Data\Streams\WATER1\Input")
    if water1:
        try:
            water1.FindNode(r"TEMP\MIXED").Value = 80.0
            water1.FindNode(r"PRES\MIXED").Value = 2.0  
            water1.FindNode(r"TOTFLOW\MIXED").Value = 1000.0
            
            # Set composition
            frac_node = water1.FindNode(r"FLOW\MIXED\WATER")
            if frac_node:
                frac_node.Value = 1000.0  # All flow is water
                print("  [OK] Set WATER1: 80C, 2bar, 1000kg/hr")
            else:
                print("  [WARN] Could not set WATER1 composition")
        except Exception as e:
            print(f"  [ERROR] Setting WATER1: {e}")
    
    # WATER2: Cold water
    water2 = aspen.Tree.FindNode(r"\Data\Streams\WATER2\Input")
    if water2:
        try:
            water2.FindNode(r"TEMP\MIXED").Value = 20.0
            water2.FindNode(r"PRES\MIXED").Value = 2.0
            water2.FindNode(r"TOTFLOW\MIXED").Value = 1000.0
            
            # Set composition
            frac_node = water2.FindNode(r"FLOW\MIXED\WATER")
            if frac_node:
                frac_node.Value = 1000.0
                print("  [OK] Set WATER2: 20C, 2bar, 1000kg/hr")
            else:
                print("  [WARN] Could not set WATER2 composition")
        except Exception as e:
            print(f"  [ERROR] Setting WATER2: {e}")
            
except Exception as e:
    print(f"  [ERROR] {e}")

# Step 9: Run Simulation
print("\n[9] Running Simulation...")
try:
    # Check if flowsheet is complete
    print("  [INFO] Sending run command...")
    aspen.Engine.Run2()
    print("  [OK] Run command sent")
    
    print("  [WAIT] Waiting 15 seconds for convergence...")
    time.sleep(15)
    
except Exception as e:
    print(f"  [ERROR] {e}")

# Step 10: Check Results
print("\n[10] Checking Results...")
try:
    out_stream = aspen.Tree.FindNode(r"\Data\Streams\OUT\Output")
    
    if out_stream:
        # Try to get temperature
        try:
            temp_node = out_stream.FindNode(r"TEMP_OUT\MIXED")
            if temp_node and temp_node.Value:
                print(f"  [OK] Temperature: {temp_node.Value} C")
            else:
                print("  [WARN] Temperature not available")
        except:
            print("  [WARN] Could not read temperature")
        
        # Try to get pressure
        try:
            pres_node = out_stream.FindNode(r"PRES_OUT\MIXED")
            if pres_node and pres_node.Value:
                print(f"  [OK] Pressure: {pres_node.Value} bar")
            else:
                print("  [WARN] Pressure not available")
        except:
            print("  [WARN] Could not read pressure")
            
        # Try to get flow
        try:
            flow_node = out_stream.FindNode(r"MASSFLMX\MIXED")
            if flow_node and flow_node.Value:
                print(f"  [OK] Mass Flow: {flow_node.Value} kg/hr")
            else:
                print("  [WARN] Mass flow not available")
        except:
            print("  [WARN] Could not read mass flow")
    else:
        print("  [FAIL] Could not find OUT stream output")
        
except Exception as e:
    print(f"  [ERROR] {e}")

print("\n" + "="*70)
print("SIMULATION COMPLETE")
print("="*70)
print("\nPlease check the Aspen Plus window to see the flowsheet.")
print("If the flowsheet is still empty, there may be a permissions issue")
print("or the COM interface may need administrator rights.")
