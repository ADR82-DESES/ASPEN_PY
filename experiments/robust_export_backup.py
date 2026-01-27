import os
import sys
import time
import csv
import win32com.client as win32

# Config
FILENAME = "automatedmixer.bkp"
# Key streams we expect to see (fallback if iteration misses them)
EXPECTED_STREAMS = ["WATER1", "WATER2", "OUT"]
TIMEOUT_SECONDS = 60

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def connect_and_load():
    log("Connecting to Aspen Plus...")
    try:
        # Using Dispatch to create/connect
        aspen = win32.Dispatch("Apwn.Document")
        
        filepath = os.path.abspath(FILENAME)
        log(f"Loading {filepath}...")
        aspen.InitFromArchive2(filepath)
        aspen.Visible = True
        aspen.SuppressDialogs = 1
        return aspen
    except Exception as e:
        log(f"Connection failed: {e}")
        return None

def run_simulation_robust(aspen):
    log("Starting asynchronous simulation...")
    try:
        # Run2(1) means Non-Blocking (asynchronous)
        aspen.Engine.Run2(1)
        
        start_time = time.time()
        while aspen.Engine.IsRunning:
            elapsed = time.time() - start_time
            if elapsed > TIMEOUT_SECONDS:
                log("TIMEOUT: Simulation took too long. Aborting.")
                aspen.Engine.Stop()
                return False
            
            time.sleep(1)
            sys.stdout.write(".")
            sys.stdout.flush()
        
        print("") # Newline
        log("Simulation completed.")
        return True
    
    except Exception as e:
        log(f"Error during run: {e}")
        return False

def get_node_value(parent_node, path_options):
    """Try multiple paths to find a value."""
    # If parent_node is None, try looking up from root if path is absolute
    # But here we assume parent_node is a stream node
    if not parent_node: return "N/A"

    for path in path_options:
        try:
            n = parent_node.FindNode(path)
            if n:
                val = n.Value
                if val is not None: 
                    return val
        except:
            pass
    return "N/A"

def process_stream(st, writer, processed_names):
    if not st: return
    try:
        name = st.Name
        if name in processed_names: return
        
        # Get Data
        # Output is preferred, Input is fallback
        # Note: Use raw strings for paths
        temp = get_node_value(st, [r"Output\TEMP_OUT\MIXED", r"Input\TEMP\MIXED", r"Input\TEMP\MIXED\1", r"Output\TEMP_OUT\MIXED\1"])
        pres = get_node_value(st, [r"Output\PRES_OUT\MIXED", r"Input\PRES\MIXED"])
        mass = get_node_value(st, [r"Output\TOTFLOW_OUT\MIXED", r"Output\MASSFLOW\MIXED", r"Input\TOTFLOW\MIXED"])
        mole = get_node_value(st, [r"Output\MOLEFLOW_OUT\MIXED", r"Input\MOLEFLOW\MIXED"])
        
        writer.writerow([name, temp, pres, mass, mole])
        processed_names.add(name)
        log(f"  Exported {name}")
    except Exception as e:
        log(f"  Error processing stream object: {e}")

def export_streams(aspen):
    out_file = "streams.csv"
    log(f"Exporting to {out_file}...")
    
    try:
        streams_node = aspen.Tree.FindNode(r"\Data\Streams")
        if not streams_node:
            log(r"Error: Could not find \Data\Streams node")
            return

        with open(out_file, 'w', newline='') as f:
            writer = csv.writer(f)
            header = ["StreamName", "Temperature (C)", "Pressure (bar)", "MassFlow (kg/hr)", "MoleFlow (kmol/hr)"]
            writer.writerow(header)
            
            processed_names = set()
            
            # Strategy 1: Iteration (Try 0-based and 1-based to covering all bases)
            count = streams_node.Elements.Count
            log(f"Found {count} streams in collection.")
            
            # Try 1 to Count (Standard COM)
            for i in range(1, count + 1):
                try:
                    st = streams_node.Elements.Item(i)
                    if st: process_stream(st, writer, processed_names)
                except: pass
            
            # Strategy 2: Explicit Lookup by Name (Fallback for 'NoneType' issues in iteration)
            for name in EXPECTED_STREAMS:
                if name not in processed_names:
                    try:
                        st = streams_node.Elements.Item(name)
                        if st: 
                            process_stream(st, writer, processed_names)
                        else:
                            log(f"  Warning: Expected stream '{name}' not found by name.")
                    except:
                        pass

        log(f"Export finished. Total unique streams: {len(processed_names)}")
        
    except Exception as e:
        log(f"Export failed: {e}")

def main():
    aspen = connect_and_load()
    if not aspen: return
    
    try:
        success = run_simulation_robust(aspen)
        if success:
            export_streams(aspen)
        else:
            log("Skipping export due to run failure.")
            
    finally:
        log("Closing Aspen Plus...")
        try:
            # Quit ensures the process terminates, preventing stacking
            aspen.Quit()
        except:
            pass
        log("Done.")

if __name__ == "__main__":
    main()
