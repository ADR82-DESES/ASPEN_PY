"""
ASPEN PLUS DIAGNOSTIC SUITE - Part 1: Connection & Version Info
This script gathers detailed information about your Aspen Plus installation
"""
import win32com.client as win32
import sys
import os

print("="*80)
print("ASPEN PLUS DIAGNOSTIC SUITE - PART 1: SYSTEM INFO")
print("="*80)

# Test 1: Connection Methods
print("\n[TEST 1] Testing Connection Methods")
print("-"*80)

connection_methods = [
    ("GetActiveObject", lambda: win32.GetActiveObject("Apwn.Document")),
    ("Dispatch", lambda: win32.Dispatch("Apwn.Document")),
    ("DispatchEx", lambda: win32.DispatchEx("Apwn.Document")),
]

aspen = None
successful_method = None

for method_name, method_func in connection_methods:
    print(f"\nTrying {method_name}...")
    try:
        test_aspen = method_func()
        print(f"  [OK] {method_name} succeeded")
        
        # Test if we can access properties
        try:
            name = test_aspen.Name
            print(f"  [OK] Can access properties: {name}")
            if not aspen:
                aspen = test_aspen
                successful_method = method_name
        except Exception as e:
            print(f"  [WARN] Cannot access properties: {e}")
            
    except Exception as e:
        print(f"  [FAIL] {method_name} failed: {e}")

if not aspen:
    print("\n[FATAL] Could not connect to Aspen Plus!")
    print("Please ensure Aspen Plus is running.")
    sys.exit(1)

print(f"\n[SUCCESS] Using {successful_method} for remaining tests")

# Test 2: Version and Build Info
print("\n[TEST 2] Aspen Plus Version Information")
print("-"*80)

version_properties = [
    ("Name", "name"),
    ("Version", "version"),
    ("Application.Name", "application_name"),
    ("Application.Version", "application_version"),
]

for prop_name, attr_path in version_properties:
    try:
        # Navigate the attribute path
        obj = aspen
        for attr in attr_path.split('.'):
            obj = getattr(obj, attr.title().replace('_', ''), None)
            if obj is None:
                break
        
        if obj is not None:
            print(f"  {prop_name}: {obj}")
        else:
            # Try direct attribute access
            try:
                parts = attr_path.split('.')
                if len(parts) == 1:
                    val = getattr(aspen, parts[0].title(), None)
                    if val:
                        print(f"  {prop_name}: {val}")
            except:
                pass
    except Exception as e:
        print(f"  {prop_name}: <not accessible>")

# Test 3: Document State
print("\n[TEST 3] Document State")
print("-"*80)

state_checks = [
    ("Visible", lambda: aspen.Visible),
    ("SuppressDialogs", lambda: aspen.SuppressDialogs),
    ("Dirty (unsaved changes)", lambda: aspen.Dirty),
]

for check_name, check_func in state_checks:
    try:
        value = check_func()
        print(f"  {check_name}: {value}")
    except Exception as e:
        print(f"  {check_name}: <error: {e}>")

# Test 4: Available Methods
print("\n[TEST 4] Available Methods & Properties")
print("-"*80)

print("\nScanning available methods...")
methods = [attr for attr in dir(aspen) if not attr.startswith('_')]
print(f"  Total public methods/properties: {len(methods)}")

# Key methods we're interested in
key_methods = [
    "Tree", "Engine", "Visible", "SuppressDialogs",
    "InitFromArchive2", "InitFromTemplate2", "Save", "SaveAs",
    "Run", "Run2", "Reinit"
]

print("\nChecking for key methods:")
for method in key_methods:
    has_it = hasattr(aspen, method)
    status = "[OK]" if has_it else "[MISSING]"
    print(f"  {status} {method}")

# Test 5: Tree Access
print("\n[TEST 5] Tree Structure Access")
print("-"*80)

try:
    tree = aspen.Tree
    print(f"  [OK] Tree object accessible: {tree}")
    
    # Try to access root node
    try:
        root = tree.FindNode(r"\Data")
        if root:
            print(f"  [OK] Can access \\Data node")
            
            # Try to get children
            try:
                if hasattr(root, 'Elements'):
                    count = root.Elements.Count
                    print(f"  [OK] \\Data has {count} child elements")
                    
                    # List first few children
                    print("\n  First 10 child nodes:")
                    for i in range(min(count, 10)):
                        try:
                            child = root.Elements.Item(i)
                            print(f"    - {child.Name}")
                        except:
                            pass
            except Exception as e:
                print(f"  [WARN] Cannot enumerate children: {e}")
        else:
            print(f"  [WARN] \\Data node not found (document may be empty)")
            
    except Exception as e:
        print(f"  [ERROR] Cannot access \\Data node: {e}")
        
except Exception as e:
    print(f"  [ERROR] Cannot access Tree: {e}")

# Test 6: Engine Access
print("\n[TEST 6] Simulation Engine Access")
print("-"*80)

try:
    engine = aspen.Engine
    print(f"  [OK] Engine object accessible: {engine}")
    
    # Check engine methods
    engine_methods = ["Run", "Run2", "Reinit", "Stop"]
    for method in engine_methods:
        has_it = hasattr(engine, method)
        status = "[OK]" if has_it else "[MISSING]"
        print(f"  {status} Engine.{method}")
        
except Exception as e:
    print(f"  [ERROR] Cannot access Engine: {e}")

# Test 7: File Operations
print("\n[TEST 7] File Operations Capability")
print("-"*80)

file_ops = [
    ("InitFromArchive2", "Load from .bkp file"),
    ("InitFromTemplate2", "Load from template"),
    ("Save", "Save current file"),
    ("SaveAs", "Save as new file"),
]

for method, description in file_ops:
    has_it = hasattr(aspen, method)
    status = "[OK]" if has_it else "[MISSING]"
    print(f"  {status} {method:20s} - {description}")

# Summary
print("\n" + "="*80)
print("DIAGNOSTIC SUMMARY")
print("="*80)
print(f"Connection Method: {successful_method}")
print(f"Tree Access: {'Available' if hasattr(aspen, 'Tree') else 'Not Available'}")
print(f"Engine Access: {'Available' if hasattr(aspen, 'Engine') else 'Not Available'}")
print(f"Document State: {'Initialized' if aspen.Tree.FindNode(r'\\Data') else 'Empty'}")
print("="*80)

print("\nPart 1 complete. Run diagnostic_part2.py for tree exploration.")
