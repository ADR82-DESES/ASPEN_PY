"""
ASPEN PLUS DIAGNOSTIC SUITE - Part 3: Flowsheet Creation Test
This script attempts to programmatically create a complete flowsheet
"""
import win32com.client as win32
import time

print("="*80)
print("ASPEN PLUS DIAGNOSTIC SUITE - PART 3: FLOWSHEET CREATION")
print("="*80)

# Connect
print("\nConnecting to Aspen Plus...")
try:
    aspen = win32.Dispatch("Apwn.Document")
    print(f"[OK] Connected: {aspen.Name}")
    aspen.Visible = True
    aspen.SuppressDialogs = 1
except Exception as e:
    print(f"[FAIL] {e}")
    exit(1)

# Track success/failure
results = {
    "components": False,
    "property_method": False,
    "streams": False,
    "blocks": False,
    "connections": False,
    "inputs": False,
    "simulation": False,
    "outputs": False
}

# Step 1: Components
print("\n[STEP 1] Adding Components")
print("-"*80)

component_approaches = [
    {
        "name": "Approach 1: Direct CAG_IDS.Elements.Add",
        "func": lambda: aspen.Tree.FindNode(r"\Data\Components\Specifications\Input\CAG_IDS").Elements.Add("WATER")
    },
    {
        "name": "Approach 2: Via Components node",
        "func": lambda: aspen.Tree.FindNode(r"\Data\Components").Elements.Add("WATER")
    },
    {
        "name": "Approach 3: Using component list",
        "func": lambda: aspen.Tree.FindNode(r"\Data\Components\Specifications\Input").Elements.Add("WATER")
    },
]

for approach in component_approaches:
    print(f"\nTrying: {approach['name']}")
    try:
        approach['func']()
        print("  [OK] Success!")
        results["components"] = True
        break
    except Exception as e:
        print(f"  [FAIL] {str(e)[:100]}")

# Step 2: Property Method
print("\n[STEP 2] Setting Property Method")
print("-"*80)

property_approaches = [
    {
        "name": "Approach 1: Direct METHOD node",
        "func": lambda: setattr(aspen.Tree.FindNode(r"\Data\Properties\Global\Input\METHOD"), 'Value', "IDEAL")
    },
    {
        "name": "Approach 2: Via Properties Specifications",
        "func": lambda: aspen.Tree.FindNode(r"\Data\Properties\Specifications\Input\PROP-SET").Elements.Add("IDEAL")
    },
]

for approach in property_approaches:
    print(f"\nTrying: {approach['name']}")
    try:
        approach['func']()
        print("  [OK] Success!")
        results["property_method"] = True
        break
    except Exception as e:
        print(f"  [FAIL] {str(e)[:100]}")

# Step 3: Create Streams
print("\n[STEP 3] Creating Streams")
print("-"*80)

stream_names = ["WATER1", "WATER2", "OUT"]
streams_created = 0

stream_approaches = [
    {
        "name": "Approach 1: Streams.Elements.Add(name)",
        "func": lambda name: aspen.Tree.FindNode(r"\Data\Streams").Elements.Add(name)
    },
    {
        "name": "Approach 2: Streams.Elements.Add(name, 'MATERIAL')",
        "func": lambda name: aspen.Tree.FindNode(r"\Data\Streams").Elements.Add(name, "MATERIAL")
    },
]

for stream_name in stream_names:
    print(f"\nCreating stream: {stream_name}")
    for approach in stream_approaches:
        try:
            approach['func'](stream_name)
            print(f"  [OK] {approach['name']} succeeded")
            streams_created += 1
            break
        except Exception as e:
            print(f"  [FAIL] {approach['name']}: {str(e)[:80]}")

results["streams"] = (streams_created == len(stream_names))
print(f"\nStreams created: {streams_created}/{len(stream_names)}")

# Step 4: Create Mixer Block
print("\n[STEP 4] Creating Mixer Block")
print("-"*80)

block_approaches = [
    {
        "name": "Approach 1: Blocks.Elements.Add('MIXER')",
        "func": lambda: aspen.Tree.FindNode(r"\Data\Blocks").Elements.Add("MIXER")
    },
    {
        "name": "Approach 2: Blocks.Elements.Add('MIXER', 'Mixer')",
        "func": lambda: aspen.Tree.FindNode(r"\Data\Blocks").Elements.Add("MIXER", "Mixer")
    },
    {
        "name": "Approach 3: Blocks.Elements.Add('MIXER', 'MIXER')",
        "func": lambda: aspen.Tree.FindNode(r"\Data\Blocks").Elements.Add("MIXER", "MIXER")
    },
]

for approach in block_approaches:
    print(f"\nTrying: {approach['name']}")
    try:
        approach['func']()
        print("  [OK] Success!")
        results["blocks"] = True
        break
    except Exception as e:
        print(f"  [FAIL] {str(e)[:100]}")

# Step 5: Connect Streams to Mixer
print("\n[STEP 5] Connecting Streams to Mixer")
print("-"*80)

if results["blocks"] and results["streams"]:
    connection_approaches = [
        {
            "name": "Approach 1: Via Input\\FEED and Output\\PROD",
            "inlet_path": r"\Data\Blocks\MIXER\Input\FEED",
            "outlet_path": r"\Data\Blocks\MIXER\Output\PROD"
        },
        {
            "name": "Approach 2: Via Ports\\F(IN) and Ports\\P(OUT)",
            "inlet_path": r"\Data\Blocks\MIXER\Ports\F(IN)",
            "outlet_path": r"\Data\Blocks\MIXER\Ports\P(OUT)"
        },
        {
            "name": "Approach 3: Via Connections",
            "inlet_path": r"\Data\Blocks\MIXER\Connections\Inlet",
            "outlet_path": r"\Data\Blocks\MIXER\Connections\Outlet"
        },
    ]
    
    for approach in connection_approaches:
        print(f"\nTrying: {approach['name']}")
        try:
            # Connect inlets
            inlet_node = aspen.Tree.FindNode(approach['inlet_path'])
            if inlet_node:
                inlet_node.Elements.Add("WATER1")
                inlet_node.Elements.Add("WATER2")
                print("  [OK] Connected inlets")
                
                # Connect outlet
                outlet_node = aspen.Tree.FindNode(approach['outlet_path'])
                if outlet_node:
                    outlet_node.Elements.Add("OUT")
                    print("  [OK] Connected outlet")
                    results["connections"] = True
                    break
            else:
                print(f"  [FAIL] Inlet node not found")
        except Exception as e:
            print(f"  [FAIL] {str(e)[:100]}")
else:
    print("[SKIP] Blocks or streams not created")

# Step 6: Set Input Conditions
print("\n[STEP 6] Setting Input Conditions")
print("-"*80)

if results["streams"]:
    try:
        # WATER1
        w1 = aspen.Tree.FindNode(r"\Data\Streams\WATER1\Input")
        if w1:
            w1.FindNode(r"TEMP\MIXED").Value = 80.0
            w1.FindNode(r"PRES\MIXED").Value = 2.0
            w1.FindNode(r"TOTFLOW\MIXED").Value = 1000.0
            print("[OK] Set WATER1 conditions")
            
            # WATER2
            w2 = aspen.Tree.FindNode(r"\Data\Streams\WATER2\Input")
            if w2:
                w2.FindNode(r"TEMP\MIXED").Value = 20.0
                w2.FindNode(r"PRES\MIXED").Value = 2.0
                w2.FindNode(r"TOTFLOW\MIXED").Value = 1000.0
                print("[OK] Set WATER2 conditions")
                results["inputs"] = True
    except Exception as e:
        print(f"[FAIL] {str(e)[:100]}")
else:
    print("[SKIP] Streams not created")

# Step 7: Run Simulation
print("\n[STEP 7] Running Simulation")
print("-"*80)

if results["inputs"]:
    try:
        aspen.Engine.Run2()
        print("[OK] Run command sent")
        print("[WAIT] Waiting 10 seconds...")
        time.sleep(10)
        results["simulation"] = True
    except Exception as e:
        print(f"[FAIL] {str(e)[:100]}")
else:
    print("[SKIP] Inputs not set")

# Step 8: Extract Outputs
print("\n[STEP 8] Extracting Outputs")
print("-"*80)

if results["simulation"]:
    try:
        out = aspen.Tree.FindNode(r"\Data\Streams\OUT\Output")
        if out:
            temp = out.FindNode(r"TEMP_OUT\MIXED").Value
            print(f"[OK] Temperature: {temp} C")
            results["outputs"] = True
    except Exception as e:
        print(f"[FAIL] {str(e)[:100]}")
else:
    print("[SKIP] Simulation not run")

# Final Summary
print("\n" + "="*80)
print("DIAGNOSTIC SUMMARY")
print("="*80)

for step, success in results.items():
    status = "[OK]" if success else "[FAIL]"
    print(f"{status} {step.replace('_', ' ').title()}")

success_count = sum(results.values())
total_count = len(results)
success_rate = (success_count / total_count) * 100

print(f"\nOverall Success Rate: {success_count}/{total_count} ({success_rate:.1f}%)")

if success_rate == 100:
    print("\n✓ FULL AUTOMATION IS POSSIBLE!")
elif success_rate >= 50:
    print("\n⚠ PARTIAL AUTOMATION IS POSSIBLE")
    print("Some manual steps may be required")
else:
    print("\n✗ MANUAL SETUP REQUIRED")
    print("Programmatic flowsheet creation is limited")

print("\n" + "="*80)
print("Check Aspen Plus window to see what was created")
print("="*80)
