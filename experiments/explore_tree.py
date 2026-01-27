import win32com.client as win32

print("=" * 70)
print("ASPEN PLUS TREE EXPLORER")
print("=" * 70)

# Connect
print("\n[1] Connecting to Aspen Plus...")
try:
    aspen = win32.Dispatch("Apwn.Document")
    print(f"  [OK] Connected: {aspen.Name}")
except Exception as e:
    print(f"  [FAIL] {e}")
    exit(1)

def explore_node(node, indent=0, max_depth=3, current_depth=0):
    """Recursively explore a node and print its structure"""
    if current_depth >= max_depth:
        return
    
    try:
        # Try to get child nodes
        if hasattr(node, 'Elements'):
            count = node.Elements.Count
            if count > 0:
                print("  " * indent + f"  [Elements: {count}]")
                for i in range(min(count, 10)):  # Limit to first 10
                    try:
                        item = node.Elements.Item(i)
                        name = item.Name if hasattr(item, 'Name') else f"Item_{i}"
                        print("  " * indent + f"    - {name}")
                        
                        # Check if it has a value
                        if hasattr(item, 'Value'):
                            try:
                                val = item.Value
                                if val is not None:
                                    print("  " * indent + f"      = {val}")
                            except:
                                pass
                    except:
                        pass
    except:
        pass

# Explore key paths
paths_to_explore = [
    r"\Data\Streams\OUT",
    r"\Data\Streams\OUT\Output",
    r"\Data\Streams\OUT\Output\TEMP_OUT",
    r"\Data\Streams\OUT\Output\TEMP",
    r"\Data\Blocks\MIXER",
]

print("\n[2] Exploring Tree Structure...")
for path in paths_to_explore:
    print(f"\n--- Path: {path} ---")
    try:
        node = aspen.Tree.FindNode(path)
        if node:
            print(f"  [OK] Node found")
            
            # Try to get value
            if hasattr(node, 'Value'):
                try:
                    val = node.Value
                    print(f"  Value: {val}")
                except Exception as e:
                    print(f"  Value: <error: {e}>")
            
            # Explore children
            explore_node(node, indent=1, max_depth=2)
        else:
            print(f"  [FAIL] Node not found")
    except Exception as e:
        print(f"  [ERROR] {e}")

# Check simulation status
print("\n[3] Checking Simulation Status...")
try:
    # Try to get run status
    status_path = r"\Data\Results Summary\Run-Status\Output\PER_ERROR"
    node = aspen.Tree.FindNode(status_path)
    if node:
        print(f"  Run Status: {node.Value}")
    
    # Try alternative status path
    status_path2 = r"\Data\Results Summary\Run-Status\Output\RUNID"
    node2 = aspen.Tree.FindNode(status_path2)
    if node2:
        print(f"  Run ID: {node2.Value}")
        
except Exception as e:
    print(f"  [ERROR] {e}")

# List all streams
print("\n[4] Listing All Streams...")
try:
    streams_node = aspen.Tree.FindNode(r"\Data\Streams")
    if streams_node and hasattr(streams_node, 'Elements'):
        count = streams_node.Elements.Count
        print(f"  Found {count} streams:")
        for i in range(count):
            try:
                stream = streams_node.Elements.Item(i)
                print(f"    - {stream.Name}")
            except:
                pass
except Exception as e:
    print(f"  [ERROR] {e}")

print("\n" + "=" * 70)
print("EXPLORATION COMPLETE")
print("=" * 70)
