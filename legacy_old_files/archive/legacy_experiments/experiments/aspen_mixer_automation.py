import os
import sys
import csv
import win32com.client as win32

# Configuration
SimulationName = "MixerSimulation.bkp"
INLET_STREAM_1 = "WATER1"
INLET_STREAM_2 = "WATER2"
OUTLET_STREAM = "OUT"
MIXER_BLOCK = "MIXER"
COMPONENT_ID = "WATER"
COMPONENT_ALIAS = "H2O"
PROPERTY_METHOD = "IDEAL" # Simple method for basic mass balance

def connect_to_aspen(visible=True):
    import time
    print("Connecting to Aspen Plus...")
    aspen = None
    
    # Method 1: Try to attach to existing active instance
    print("  Method 1: Trying GetActiveObject...")
    try:
        aspen = win32.GetActiveObject("Apwn.Document")
        print("  -> Attached to active instance.")
        
        # Verify it's valid
        try:
            _ = aspen.Name
            print(f"  -> Document name: {aspen.Name}")
        except:
            print("  -> Attached object invalid.")
            aspen = None
    except Exception as e:
        print(f"  -> GetActiveObject failed: {e}")
    
    # Method 2: Try Dispatch (creates new instance or connects to existing)
    if not aspen:
        print("  Method 2: Trying Dispatch...")
        try:
            aspen = win32.Dispatch("Apwn.Document")
            print("  -> Dispatch successful.")
            
            # Verify
            try:
                _ = aspen.Name
                print(f"  -> Document name: {aspen.Name}")
            except:
                print("  -> Dispatch created object but it's not ready.")
                aspen = None
        except Exception as e:
            print(f"  -> Dispatch failed: {e}")
    
    # Method 3: Try DispatchEx with specific flags
    if not aspen:
        print("  Method 3: Trying DispatchEx...")
        try:
            aspen = win32.DispatchEx("Apwn.Document")
            print("  -> DispatchEx successful.")
            
            # Verify
            try:
                _ = aspen.Name
                print(f"  -> Document name: {aspen.Name}")
            except:
                print("  -> DispatchEx created object but it's not ready.")
                aspen = None
        except Exception as e:
            print(f"  -> DispatchEx failed: {e}")
    
    if not aspen:
        print("\n  *** ERROR: Could not connect to Aspen Plus ***")
        print("  Troubleshooting steps:")
        print("  1. Ensure Aspen Plus is installed correctly")
        print("  2. Open Aspen Plus manually")
        print("  3. Create a NEW blank simulation (File -> New)")
        print("  4. Save it as 'test.bkp' in this directory")
        print("  5. Keep Aspen Plus open with the simulation loaded")
        print("  6. Run this script again")
        return None

    try:
        aspen.Visible = visible
        aspen.SuppressDialogs = 1
        print("  -> Connection successful!")
    except Exception as e:
        print(f"  -> Warning setting properties: {e}")
    
    return aspen

def define_components(aspen):
    print("Defining Components...")
    try:
        # Navigate to Components Input root
        base_path = r"\Data\Components\Specifications\Input"
        input_node = aspen.Tree.FindNode(base_path)
        
        if not input_node:
             print("  ERROR: Components input node not found.")
             return

        # 1. Add Component ID
        # The CAG_IDS node is usually a vector/collection.
        # Try adding the component ID directly.
        cag_ids = input_node.FindNode("CAG_IDS")
        if cag_ids:
            try:
                # Check if it exists by trying to access it (Aspen often returns the node if mapped)
                # If specific ID node doesn't exist, we add it.
                # However, FindNode("WATER") on CAG_IDS vector might fail if not there.
                
                # Check specific instance path
                check = aspen.Tree.FindNode(base_path + rf"\CAG_IDS\{COMPONENT_ID}")
                if check:
                    print(f"  -> Component {COMPONENT_ID} already exists.")
                else:
                    # Add it
                    cag_ids.Elements.Add(COMPONENT_ID)
                    print(f"  -> Added Component ID: {COMPONENT_ID}")
            except Exception as e:
                print(f"  Note adding ID: {e}")

        # 2. Set Alias / Name
        # Once added, we can modify properties
        try:
             # Alias (H2O)
             aspen.Tree.FindNode(base_path + rf"\CAG_ALIAS\{COMPONENT_ID}").Value = COMPONENT_ALIAS
             # Name
             aspen.Tree.FindNode(base_path + rf"\CAG_NAME\{COMPONENT_ID}").Value = "Water"
             print(f"  -> Set Alias {COMPONENT_ALIAS}")
        except Exception as e:
             print(f"  Warning setting alias: {e}")

    except Exception as e:
        print(f"  Error in define_components: {e}")

def set_property_method(aspen):
    print(f"Setting Property Method to {PROPERTY_METHOD}...")
    try:
        # Global Method Path
        # Common: \Data\Properties\Global\Input\METHOD
        path_global = r"\Data\Properties\Global\Input\METHOD"
        node = aspen.Tree.FindNode(path_global)
        
        if node:
            node.Value = PROPERTY_METHOD
        else:
             print(f"  Warning: Global Method node not found at {path_global}")
             # Try finding the Specifications folder
             specs = aspen.Tree.FindNode(r"\Data\Properties\Global\Input")
             if specs:
                 # Sometimes one must add the method to the list first?
                 pass
             
        print("  -> Property method set (or attempted).")
    except Exception as e:
        print(f"  Warning setting property method: {e}")



def create_flowsheet(aspen):
    print("Building Flowsheet...")
    try:
        blocks = aspen.Tree.FindNode(r"\Data\Blocks")
        try: blocks.Elements.Add(MIXER_BLOCK, "Mixer")
        except: pass 
        
        streams = aspen.Tree.FindNode(r"\Data\Streams")
        for s in [INLET_STREAM_1, INLET_STREAM_2, OUTLET_STREAM]:
            try: streams.Elements.Add(s, "MATERIAL")
            except: pass

        # Connect
        print("  Connecting streams...")
        mixer = blocks.Elements.Item(MIXER_BLOCK)
        
        # Input
        try:
            feed = mixer.FindNode(r"Input\FEED")
            for s in [INLET_STREAM_1, INLET_STREAM_2]:
                try: feed.Elements.Add(s) # Standard way
                except: pass
        except: print("  Warning: Could not access Mixer Input ports")

        # Output
        try:
            prod = mixer.FindNode(r"Output\PROD")
            try: prod.Elements.Add(OUTLET_STREAM)
            except: pass
        except: print("  Warning: Could not access Mixer Output ports")
             
    except Exception as e:
        print(f"  Error building flowsheet: {e}")

def set_inputs(aspen):
    print("Setting Inputs...")
    try:
        streams = aspen.Tree.FindNode(r"\Data\Streams")
        
        def set_stream(s_name, t, p, f):
            st = streams.Elements.Item(s_name)
            if not st: return
            
            inp = st.FindNode("Input")
            if not inp: return

            # T, P, Flow
            try: inp.FindNode(r"TEMP\MIXED").Value = t; print(f"    Set T={t} for {s_name}")
            except: pass
            try: inp.FindNode(r"PRES\MIXED").Value = p
            except: pass
            try: inp.FindNode(r"TOTFLOW\MIXED").Value = f
            except: pass
            
            # Comp
            # Path: Input\FRAC\MIXED\<ComponentID> or just index?
            # It's usually keyed by ID if ID is unique.
            try:
                frac = inp.FindNode(r"FRAC\MIXED")
                if frac:
                    # Try direct item access
                    try: frac.Elements.Item(COMPONENT_ID).Value = 1.0; print(f"    Set Comp for {s_name}")
                    except:
                        # Try adding if missing? Usually autofilled if component exists globaly
                        pass
                else:
                    print(f"    FRAC node missing on {s_name} (Components not defined?)")
            except: pass

        set_stream(INLET_STREAM_1, 80.0, 2.0, 1000.0)
        set_stream(INLET_STREAM_2, 20.0, 2.0, 1000.0)

    except Exception as e:
        print(f"  Error inputs: {e}")

def export_results_csv(aspen):
    print("Exporting results (Debug)...")
    try:
        # Get Output Stream Data
        # Base: \Data\Streams\OUT\Output
        out_base = rf"\Data\Streams\{OUTLET_STREAM}\Output"
        
        # Debug: Dump children of Output to see what's actually there
        print(f"Debug: Structure of {out_base}:")
        node = aspen.Tree.FindNode(out_base)
        if node:
            dump_tree(node, 1, 2)
        else:
             print("  Output node not found (Simulation might not have converged)")

        def get_val(suffix_list):
            for s in suffix_list:
                n = aspen.Tree.FindNode(out_base + s)
                if n: return n.Value
            return "N/A"

        # Try multiple standard paths for results
        temp = get_val([r"\TEMP_OUT\MIXED", r"\TEMP\MIXED", r"\TEMP"])
        pres = get_val([r"\PRES_OUT\MIXED", r"\PRES\MIXED", r"\PRES"])
        mass_flow = get_val([r"\TOTFLOW_OUT\MIXED", r"\MASSFLOW\MIXED", r"\TOTFLOW"])
        
        filename = "results.csv"
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Parameter", "Value", "Unit"])
            writer.writerow(["Stream", OUTLET_STREAM, "-"])
            writer.writerow(["Temperature", temp, "C"])
            writer.writerow(["Pressure", pres, "bar"])
            writer.writerow(["MassFlow", mass_flow, "kg/hr"])
            
        print(f"  -> Saved to {os.path.abspath(filename)}")
        
        # Read back for validation
        with open(filename, 'r') as f:
            print(f.read())
            
    except Exception as e:
        print(f"  Error exporting CSV: {e}")

def main():
    aspen = connect_to_aspen()
    if not aspen: return

    # Setup Steps (Create from scratch if needed)
    define_components(aspen)
    set_property_method(aspen)
    create_flowsheet(aspen)
    
    # Run Steps
    set_inputs(aspen)
    
    print("Running Simulation...")
    try:
        aspen.Engine.Run2()
        print("  -> Run command sent.")
    except Exception as e:
         print(f"  Error running simulation: {e}")

    export_results_csv(aspen)

if __name__ == "__main__":
    main()
