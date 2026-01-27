import win32com.client as win32
import time
import csv

# Open log file
log = open("simulation_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*60)
log_print("ASPEN PLUS MIXER SIMULATION")
log_print("="*60)

# Connect
log_print("\n[1] Connecting...")
try:
    aspen = win32.Dispatch("Apwn.Document")
    log_print(f"OK - Connected to: {aspen.Name}")
    aspen.Visible = True
    aspen.SuppressDialogs = 1
except Exception as e:
    log_print(f"FAIL - {e}")
    log.close()
    exit(1)

# Define components
log_print("\n[2] Defining components...")
try:
    base = r"\Data\Components\Specifications\Input"
    cag_ids = aspen.Tree.FindNode(base + r"\CAG_IDS")
    try:
        cag_ids.Elements.Add("WATER")
        log_print("OK - Added WATER")
    except:
        log_print("INFO - WATER already exists")
    
    aspen.Tree.FindNode(base + r"\CAG_ALIAS\WATER").Value = "H2O"
    log_print("OK - Set alias")
except Exception as e:
    log_print(f"ERROR - {e}")

# Set property method
log_print("\n[3] Setting property method...")
try:
    aspen.Tree.FindNode(r"\Data\Properties\Global\Input\METHOD").Value = "IDEAL"
    log_print("OK - Set to IDEAL")
except Exception as e:
    log_print(f"ERROR - {e}")

# Create flowsheet
log_print("\n[4] Creating flowsheet...")
try:
    blocks = aspen.Tree.FindNode(r"\Data\Blocks")
    streams = aspen.Tree.FindNode(r"\Data\Streams")
    
    # Add mixer
    try:
        blocks.Elements.Add("MIXER", "Mixer")
        log_print("OK - Added MIXER")
    except:
        log_print("INFO - MIXER exists")
    
    # Add streams
    for s in ["WATER1", "WATER2", "OUT"]:
        try:
            streams.Elements.Add(s, "MATERIAL")
            log_print(f"OK - Added {s}")
        except:
            log_print(f"INFO - {s} exists")
    
    # Connect
    mixer = blocks.Elements.Item("MIXER")
    feed = mixer.FindNode(r"Input\FEED")
    prod = mixer.FindNode(r"Output\PROD")
    
    for s in ["WATER1", "WATER2"]:
        try:
            feed.Elements.Add(s)
            log_print(f"OK - Connected {s}")
        except:
            log_print(f"INFO - {s} connected")
    
    try:
        prod.Elements.Add("OUT")
        log_print("OK - Connected OUT")
    except:
        log_print("INFO - OUT connected")
        
except Exception as e:
    log_print(f"ERROR - {e}")

# Set inputs
log_print("\n[5] Setting inputs...")
try:
    streams = aspen.Tree.FindNode(r"\Data\Streams")
    
    # WATER1
    st1 = streams.Elements.Item("WATER1")
    inp1 = st1.FindNode("Input")
    inp1.FindNode(r"TEMP\MIXED").Value = 80.0
    inp1.FindNode(r"PRES\MIXED").Value = 2.0
    inp1.FindNode(r"TOTFLOW\MIXED").Value = 1000.0
    inp1.FindNode(r"FRAC\MIXED").Elements.Item("WATER").Value = 1.0
    log_print("OK - WATER1: 80C, 2bar, 1000kg/hr")
    
    # WATER2
    st2 = streams.Elements.Item("WATER2")
    inp2 = st2.FindNode("Input")
    inp2.FindNode(r"TEMP\MIXED").Value = 20.0
    inp2.FindNode(r"PRES\MIXED").Value = 2.0
    inp2.FindNode(r"TOTFLOW\MIXED").Value = 1000.0
    inp2.FindNode(r"FRAC\MIXED").Elements.Item("WATER").Value = 1.0
    log_print("OK - WATER2: 20C, 2bar, 1000kg/hr")
    
except Exception as e:
    log_print(f"ERROR - {e}")

# Run simulation
log_print("\n[6] Running simulation...")
try:
    aspen.Engine.Run2()
    log_print("OK - Run command sent")
    log_print("WAIT - Waiting 10 seconds for convergence...")
    time.sleep(10)
    log_print("OK - Wait complete")
except Exception as e:
    log_print(f"ERROR - {e}")

# Extract results
log_print("\n[7] Extracting results...")
results = {}

# Try to find the output stream
try:
    out_stream = aspen.Tree.FindNode(r"\Data\Streams\OUT")
    if out_stream:
        log_print("OK - Found OUT stream")
        
        # Try Output node
        out_node = out_stream.FindNode("Output")
        if out_node:
            log_print("OK - Found Output node")
            
            # List what's in Output
            if hasattr(out_node, 'Elements'):
                count = out_node.Elements.Count
                log_print(f"INFO - Output has {count} elements")
                for i in range(min(count, 20)):
                    try:
                        elem = out_node.Elements.Item(i)
                        log_print(f"  - Element {i}: {elem.Name}")
                    except:
                        pass
            
            # Try common paths
            temp_paths = [
                r"TEMP_OUT\MIXED",
                r"TEMP\MIXED", 
                r"TEMP",
                "TEMP_OUT",
            ]
            
            for path in temp_paths:
                try:
                    node = out_node.FindNode(path)
                    if node and node.Value is not None:
                        results["Temperature"] = node.Value
                        log_print(f"OK - Temperature: {node.Value} C (from {path})")
                        break
                except:
                    pass
            
            # Similar for pressure and flow
            pres_paths = [r"PRES_OUT\MIXED", r"PRES\MIXED", r"PRES", "PRES_OUT"]
            for path in pres_paths:
                try:
                    node = out_node.FindNode(path)
                    if node and node.Value is not None:
                        results["Pressure"] = node.Value
                        log_print(f"OK - Pressure: {node.Value} bar (from {path})")
                        break
                except:
                    pass
            
            flow_paths = [r"TOTFLOW_OUT\MIXED", r"MASSFLOW\MIXED", r"TOTFLOW", "TOTFLOW_OUT"]
            for path in flow_paths:
                try:
                    node = out_node.FindNode(path)
                    if node and node.Value is not None:
                        results["MassFlow"] = node.Value
                        log_print(f"OK - MassFlow: {node.Value} kg/hr (from {path})")
                        break
                except:
                    pass
        else:
            log_print("FAIL - Output node not found")
    else:
        log_print("FAIL - OUT stream not found")
        
except Exception as e:
    log_print(f"ERROR - {e}")

# Fill in N/A for missing values
if "Temperature" not in results:
    results["Temperature"] = "N/A"
    log_print("WARN - Temperature not found")
if "Pressure" not in results:
    results["Pressure"] = "N/A"
    log_print("WARN - Pressure not found")
if "MassFlow" not in results:
    results["MassFlow"] = "N/A"
    log_print("WARN - MassFlow not found")

# Save results
log_print("\n[8] Saving results...")
try:
    with open("results.csv", 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Parameter", "Value", "Unit"])
        writer.writerow(["Stream", "OUT", "-"])
        writer.writerow(["Temperature", results["Temperature"], "C"])
        writer.writerow(["Pressure", results["Pressure"], "bar"])
        writer.writerow(["MassFlow", results["MassFlow"], "kg/hr"])
    log_print("OK - Saved to results.csv")
except Exception as e:
    log_print(f"ERROR - {e}")

log_print("\n" + "="*60)
log_print("SIMULATION COMPLETE")
log_print("="*60)
log_print("\nCheck simulation_log.txt for details")
log_print("Check results.csv for output data")

log.close()
print("\nDone! Check simulation_log.txt for full details")
