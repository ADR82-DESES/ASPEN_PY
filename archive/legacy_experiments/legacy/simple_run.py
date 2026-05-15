"""
SIMPLE ASPEN PLUS AUTOMATION
This script assumes you have MANUALLY created a flowsheet with:
- Component: WATER
- Property Method: IDEAL  
- Mixer block: MIXER
- Streams: WATER1, WATER2, OUT (connected to MIXER)

The script will:
1. Set input conditions
2. Run simulation
3. Extract results
"""
import win32com.client as win32
import time
import csv

print("\n" + "="*70)
print("ASPEN PLUS MIXER SIMULATION - SIMPLE VERSION")
print("="*70)

# Connect
print("\nConnecting to Aspen Plus...")
try:
    aspen = win32.Dispatch("Apwn.Document")
    print(f"✓ Connected to: {aspen.Name}")
except Exception as e:
    print(f"✗ Connection failed: {e}")
    print("\nMake sure Aspen Plus is running with a simulation open!")
    exit(1)

# Set inputs
print("\nSetting input conditions...")
try:
    # WATER1: Hot water (80°C, 2 bar, 1000 kg/hr)
    print("  Setting WATER1 (hot water)...")
    w1 = aspen.Tree.FindNode(r"\Data\Streams\WATER1\Input")
    if w1:
        w1.FindNode(r"TEMP\MIXED").Value = 80.0
        w1.FindNode(r"PRES\MIXED").Value = 2.0
        w1.FindNode(r"TOTFLOW\MIXED").Value = 1000.0
        w1.FindNode(r"FRAC\MIXED\WATER").Value = 1.0
        print("    ✓ WATER1: 80°C, 2 bar, 1000 kg/hr, 100% water")
    else:
        print("    ✗ WATER1 stream not found! Please create it in Aspen Plus.")
        exit(1)
    
    # WATER2: Cold water (20°C, 2 bar, 1000 kg/hr)
    print("  Setting WATER2 (cold water)...")
    w2 = aspen.Tree.FindNode(r"\Data\Streams\WATER2\Input")
    if w2:
        w2.FindNode(r"TEMP\MIXED").Value = 20.0
        w2.FindNode(r"PRES\MIXED").Value = 2.0
        w2.FindNode(r"TOTFLOW\MIXED").Value = 1000.0
        w2.FindNode(r"FRAC\MIXED\WATER").Value = 1.0
        print("    ✓ WATER2: 20°C, 2 bar, 1000 kg/hr, 100% water")
    else:
        print("    ✗ WATER2 stream not found! Please create it in Aspen Plus.")
        exit(1)
        
except Exception as e:
    print(f"  ✗ Error setting inputs: {e}")
    print("\nMake sure the flowsheet has WATER1 and WATER2 streams!")
    exit(1)

# Run simulation
print("\nRunning simulation...")
try:
    aspen.Engine.Run2()
    print("  ✓ Run command sent to Aspen Plus")
    print("  ⏳ Waiting 10 seconds for convergence...")
    time.sleep(10)
    print("  ✓ Wait complete")
except Exception as e:
    print(f"  ✗ Error running simulation: {e}")
    exit(1)

# Extract results
print("\nExtracting results from OUT stream...")
results = {
    "Temperature": "N/A",
    "Pressure": "N/A",
    "MassFlow": "N/A"
}

try:
    out = aspen.Tree.FindNode(r"\Data\Streams\OUT\Output")
    if out:
        # Try different path variations for each parameter
        # Temperature
        for path in [r"TEMP_OUT\MIXED", r"TEMP\MIXED", r"TEMP"]:
            try:
                node = out.FindNode(path)
                if node and node.Value is not None:
                    results["Temperature"] = round(node.Value, 2)
                    print(f"  ✓ Temperature: {results['Temperature']} °C")
                    break
            except:
                pass
        
        # Pressure
        for path in [r"PRES_OUT\MIXED", r"PRES\MIXED", r"PRES"]:
            try:
                node = out.FindNode(path)
                if node and node.Value is not None:
                    results["Pressure"] = round(node.Value, 2)
                    print(f"  ✓ Pressure: {results['Pressure']} bar")
                    break
            except:
                pass
        
        # Mass Flow
        for path in [r"MASSFLMX\MIXED", r"TOTFLOW\MIXED", r"TOTFLOW"]:
            try:
                node = out.FindNode(path)
                if node and node.Value is not None:
                    results["MassFlow"] = round(node.Value, 2)
                    print(f"  ✓ Mass Flow: {results['MassFlow']} kg/hr")
                    break
            except:
                pass
    else:
        print("  ✗ OUT stream not found!")
        
except Exception as e:
    print(f"  ✗ Error extracting results: {e}")

# Save results
print("\nSaving results to CSV...")
try:
    with open("results.csv", 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Parameter", "Value", "Unit"])
        writer.writerow(["Stream", "OUT", "-"])
        writer.writerow(["Temperature", results["Temperature"], "°C"])
        writer.writerow(["Pressure", results["Pressure"], "bar"])
        writer.writerow(["MassFlow", results["MassFlow"], "kg/hr"])
    print("  ✓ Results saved to results.csv")
    
    # Display results
    print("\n" + "="*70)
    print("RESULTS SUMMARY")
    print("="*70)
    print(f"  Outlet Temperature: {results['Temperature']} °C")
    print(f"  Outlet Pressure:    {results['Pressure']} bar")
    print(f"  Outlet Mass Flow:   {results['MassFlow']} kg/hr")
    print("="*70)
    
    # Expected result
    print("\nExpected: Mixed temperature should be ~50°C (average of 80°C and 20°C)")
    
except Exception as e:
    print(f"  ✗ Error saving results: {e}")

print("\n✓ SIMULATION COMPLETE!\n")
