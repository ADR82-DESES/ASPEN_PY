import win32com.client as win32
import os

def find_node_by_name(node, target_name, max_depth=12, depth=0):
    if depth > max_depth:
        return
    
    try:
        # Some nodes have .Name, some might use .name
        name = None
        try: name = node.Name
        except: pass
        
        if name == target_name:
            print(f"FOUND: {node.Path}")
            # Try to get value too
            try: print(f"  Value: {node.Value}")
            except: pass
        
        if hasattr(node, "Elements"):
            for i in range(node.Elements.Count):
                find_node_by_name(node.Elements.Item(i), target_name, max_depth, depth + 1)
    except:
        pass

def main():
    apw_path = os.path.abspath(r"Methanol Plant\MethanolPlant_ready.apw")
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitFromArchive2(apw_path)
        
        print(f"Searching for selection and active nodes in {apw_path}...")
        root = aspen.Tree.FindNode(r"\Data")
        for target in ["PER_ERROR", "Selection", "Active", "BLKSTAT"]:
             find_node_by_name(root, target, max_depth=10)
        
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
