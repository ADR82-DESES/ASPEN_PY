"""
ASPEN PLUS SIMPLE DIAGNOSTIC
A simplified diagnostic that saves all output to a file
"""
import win32com.client as win32
import sys
import traceback

# Open log file
log_file = open("diagnostic_output.txt", "w", encoding="utf-8")

def log(msg):
    """Print and log"""
    print(msg)
    log_file.write(msg + "\n")
    log_file.flush()

log("="*70)
log("ASPEN PLUS SIMPLE DIAGNOSTIC")
log("="*70)

# Test 1: Connection
log("\n[TEST 1] Connection")
log("-"*70)

aspen = None
try:
    aspen = win32.Dispatch("Apwn.Document")
    log("[OK] Connected via Dispatch")
    
    try:
        name = aspen.Name
        log(f"[OK] Document Name: {name}")
    except Exception as e:
        log(f"[WARN] Cannot read Name: {e}")
        
except Exception as e:
    log(f"[FAIL] Connection failed: {e}")
    log_file.close()
    sys.exit(1)

# Test 2: Basic Properties
log("\n[TEST 2] Basic Properties")
log("-"*70)

properties_to_test = ["Visible", "SuppressDialogs", "Dirty"]

for prop in properties_to_test:
    try:
        val = getattr(aspen, prop, None)
        log(f"[OK] {prop}: {val}")
    except Exception as e:
        log(f"[FAIL] {prop}: {e}")

# Test 3: Tree Access
log("\n[TEST 3] Tree Access")
log("-"*70)

try:
    tree = aspen.Tree
    log("[OK] Tree object accessible")
    
    # Try to access Data node
    try:
        data_node = tree.FindNode(r"\Data")
        if data_node:
            log("[OK] \\Data node found")
            
            # Try to count children
            try:
                if hasattr(data_node, 'Elements'):
                    count = data_node.Elements.Count
                    log(f"[OK] \\Data has {count} children")
                    
                    # List first 5
                    log("\nFirst 5 child nodes:")
                    for i in range(min(5, count)):
                        try:
                            child = data_node.Elements.Item(i)
                            log(f"  {i+1}. {child.Name}")
                        except:
                            log(f"  {i+1}. <error accessing>")
                else:
                    log("[INFO] Data node has no Elements attribute")
            except Exception as e:
                log(f"[WARN] Cannot enumerate children: {e}")
        else:
            log("[WARN] \\Data node not found (document may be empty)")
    except Exception as e:
        log(f"[FAIL] Cannot access \\Data: {e}")
        
except Exception as e:
    log(f"[FAIL] Cannot access Tree: {e}")

# Test 4: Engine Access
log("\n[TEST 4] Engine Access")
log("-"*70)

try:
    engine = aspen.Engine
    log("[OK] Engine accessible")
    
    # Check for Run methods
    has_run = hasattr(engine, 'Run')
    has_run2 = hasattr(engine, 'Run2')
    log(f"[INFO] Has Run method: {has_run}")
    log(f"[INFO] Has Run2 method: {has_run2}")
    
except Exception as e:
    log(f"[FAIL] Cannot access Engine: {e}")

# Test 5: Key Nodes
log("\n[TEST 5] Key Node Paths")
log("-"*70)

key_paths = [
    r"\Data\Components",
    r"\Data\Properties",
    r"\Data\Streams",
    r"\Data\Blocks",
]

for path in key_paths:
    try:
        node = aspen.Tree.FindNode(path)
        if node:
            log(f"[OK] {path}")
            
            # Try to get count
            try:
                if hasattr(node, 'Elements'):
                    count = node.Elements.Count
                    log(f"     ({count} elements)")
            except:
                pass
        else:
            log(f"[MISSING] {path}")
    except Exception as e:
        log(f"[ERROR] {path}: {str(e)[:50]}")

# Test 6: Can we add a component?
log("\n[TEST 6] Component Creation Test")
log("-"*70)

try:
    comp_node = aspen.Tree.FindNode(r"\Data\Components\Specifications\Input\CAG_IDS")
    if comp_node:
        log("[OK] Component node found")
        
        # Try to add TEST component
        try:
            comp_node.Elements.Add("TESTCOMP")
            log("[OK] Successfully added TESTCOMP")
            
            # Try to remove it
            try:
                comp_node.Elements.Remove("TESTCOMP")
                log("[OK] Successfully removed TESTCOMP")
            except Exception as e:
                log(f"[WARN] Could not remove: {e}")
                
        except Exception as e:
            log(f"[FAIL] Cannot add component: {str(e)[:100]}")
    else:
        log("[MISSING] Component node not found")
        
except Exception as e:
    log(f"[ERROR] {str(e)[:100]}")

# Test 7: Can we add a stream?
log("\n[TEST 7] Stream Creation Test")
log("-"*70)

try:
    streams_node = aspen.Tree.FindNode(r"\Data\Streams")
    if streams_node:
        log("[OK] Streams node found")
        
        # Try to add TEST stream
        try:
            streams_node.Elements.Add("TESTSTREAM")
            log("[OK] Successfully added TESTSTREAM")
            
            # Try to remove it
            try:
                streams_node.Elements.Remove("TESTSTREAM")
                log("[OK] Successfully removed TESTSTREAM")
            except Exception as e:
                log(f"[WARN] Could not remove: {e}")
                
        except Exception as e:
            log(f"[FAIL] Cannot add stream: {str(e)[:100]}")
    else:
        log("[MISSING] Streams node not found")
        
except Exception as e:
    log(f"[ERROR] {str(e)[:100]}")

# Summary
log("\n" + "="*70)
log("DIAGNOSTIC COMPLETE")
log("="*70)
log("\nResults saved to diagnostic_output.txt")
log("Please review the file for full details.")

log_file.close()

print("\n✓ Diagnostic complete! Check diagnostic_output.txt for results.")
