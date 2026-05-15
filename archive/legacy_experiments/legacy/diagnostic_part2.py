"""
ASPEN PLUS DIAGNOSTIC SUITE - Part 2: Tree Structure Exploration
This script explores the tree structure to understand what nodes are available
"""
import win32com.client as win32
import json

print("="*80)
print("ASPEN PLUS DIAGNOSTIC SUITE - PART 2: TREE EXPLORATION")
print("="*80)

# Connect
print("\nConnecting to Aspen Plus...")
try:
    aspen = win32.Dispatch("Apwn.Document")
    print(f"[OK] Connected")
except Exception as e:
    print(f"[FAIL] {e}")
    exit(1)

def explore_node(path, max_depth=3, current_depth=0, indent=0):
    """Recursively explore a node and its children"""
    if current_depth >= max_depth:
        return
    
    prefix = "  " * indent
    
    try:
        node = aspen.Tree.FindNode(path)
        if not node:
            print(f"{prefix}[NOT FOUND] {path}")
            return
        
        print(f"{prefix}[NODE] {path}")
        
        # Try to get value
        if hasattr(node, 'Value'):
            try:
                val = node.Value
                if val is not None:
                    val_str = str(val)[:50]  # Truncate long values
                    print(f"{prefix}  Value: {val_str}")
            except:
                pass
        
        # Try to get children
        if hasattr(node, 'Elements'):
            try:
                count = node.Elements.Count
                if count > 0:
                    print(f"{prefix}  Children: {count}")
                    
                    # List children (limit to 15)
                    for i in range(min(count, 15)):
                        try:
                            child = node.Elements.Item(i)
                            child_name = child.Name
                            child_path = f"{path}\\{child_name}"
                            
                            # Recursively explore (but limit depth)
                            if current_depth < max_depth - 1:
                                explore_node(child_path, max_depth, current_depth + 1, indent + 1)
                            else:
                                print(f"{prefix}    - {child_name}")
                        except Exception as e:
                            print(f"{prefix}    - [Error accessing child {i}]")
                    
                    if count > 15:
                        print(f"{prefix}    ... and {count - 15} more")
            except Exception as e:
                print(f"{prefix}  [Cannot enumerate children: {e}]")
                
    except Exception as e:
        print(f"{prefix}[ERROR] {path}: {e}")

# Test key paths
print("\n[TEST 1] Exploring Key Paths")
print("-"*80)

key_paths = [
    r"\Data",
    r"\Data\Components",
    r"\Data\Properties",
    r"\Data\Streams",
    r"\Data\Blocks",
    r"\Data\Flowsheeting Options",
]

for path in key_paths:
    print(f"\nExploring: {path}")
    explore_node(path, max_depth=2)

# Test if we can create nodes
print("\n[TEST 2] Testing Node Creation Capability")
print("-"*80)

creation_tests = [
    {
        "name": "Create Component",
        "path": r"\Data\Components\Specifications\Input\CAG_IDS",
        "action": lambda node: node.Elements.Add("TEST_COMP"),
        "cleanup": lambda node: node.Elements.Remove("TEST_COMP")
    },
    {
        "name": "Create Stream",
        "path": r"\Data\Streams",
        "action": lambda node: node.Elements.Add("TEST_STREAM"),
        "cleanup": lambda node: node.Elements.Remove("TEST_STREAM")
    },
    {
        "name": "Create Block",
        "path": r"\Data\Blocks",
        "action": lambda node: node.Elements.Add("TEST_BLOCK"),
        "cleanup": lambda node: node.Elements.Remove("TEST_BLOCK")
    },
]

for test in creation_tests:
    print(f"\nTesting: {test['name']}")
    try:
        node = aspen.Tree.FindNode(test['path'])
        if node:
            print(f"  [OK] Found node: {test['path']}")
            
            # Try to create
            try:
                test['action'](node)
                print(f"  [OK] Creation succeeded!")
                
                # Try to clean up
                try:
                    test['cleanup'](node)
                    print(f"  [OK] Cleanup succeeded")
                except Exception as e:
                    print(f"  [WARN] Cleanup failed: {e}")
                    
            except Exception as e:
                print(f"  [FAIL] Creation failed: {e}")
        else:
            print(f"  [FAIL] Node not found: {test['path']}")
            
    except Exception as e:
        print(f"  [ERROR] {e}")

# Test property access
print("\n[TEST 3] Testing Property Method Access")
print("-"*80)

property_paths = [
    r"\Data\Properties\Global\Input",
    r"\Data\Properties\Global\Input\METHOD",
    r"\Data\Properties\Methods",
]

for path in property_paths:
    print(f"\nChecking: {path}")
    try:
        node = aspen.Tree.FindNode(path)
        if node:
            print(f"  [OK] Node exists")
            
            # Try to get/set value
            if hasattr(node, 'Value'):
                try:
                    val = node.Value
                    print(f"  Current value: {val}")
                    
                    # Try to set (if it's the METHOD node)
                    if "METHOD" in path:
                        try:
                            original = val
                            node.Value = "IDEAL"
                            print(f"  [OK] Can set value to IDEAL")
                            # Restore
                            if original:
                                node.Value = original
                        except Exception as e:
                            print(f"  [FAIL] Cannot set value: {e}")
                except Exception as e:
                    print(f"  [WARN] Cannot access value: {e}")
        else:
            print(f"  [FAIL] Node not found")
    except Exception as e:
        print(f"  [ERROR] {e}")

# Test stream structure
print("\n[TEST 4] Exploring Stream Structure (if any streams exist)")
print("-"*80)

try:
    streams = aspen.Tree.FindNode(r"\Data\Streams")
    if streams and hasattr(streams, 'Elements'):
        count = streams.Elements.Count
        print(f"Found {count} streams")
        
        if count > 0:
            # Explore first stream
            first_stream = streams.Elements.Item(0)
            stream_name = first_stream.Name
            print(f"\nExploring first stream: {stream_name}")
            
            stream_paths = [
                f"\\Data\\Streams\\{stream_name}\\Input",
                f"\\Data\\Streams\\{stream_name}\\Output",
                f"\\Data\\Streams\\{stream_name}\\Input\\TEMP",
                f"\\Data\\Streams\\{stream_name}\\Input\\PRES",
            ]
            
            for path in stream_paths:
                explore_node(path, max_depth=2, indent=1)
        else:
            print("No streams exist in the flowsheet")
    else:
        print("Streams node not accessible or empty")
except Exception as e:
    print(f"[ERROR] {e}")

# Save results
print("\n[TEST 5] Saving Diagnostic Results")
print("-"*80)

results = {
    "connection": "Success",
    "tree_accessible": hasattr(aspen, 'Tree'),
    "engine_accessible": hasattr(aspen, 'Engine'),
}

try:
    with open("diagnostic_results.json", 'w') as f:
        json.dump(results, f, indent=2)
    print("[OK] Results saved to diagnostic_results.json")
except Exception as e:
    print(f"[WARN] Could not save results: {e}")

print("\n" + "="*80)
print("PART 2 COMPLETE")
print("="*80)
print("\nRun diagnostic_part3.py to test programmatic flowsheet creation")
