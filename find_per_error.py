import win32com.client as win32
import os

def find_node_by_name(node, target_name, max_depth=10, depth=0):
    if depth > max_depth:
        return
    
    try:
        # Check if node has a name and it matches
        name = node.Name if hasattr(node, "Name") else getattr(node, "name", None)
        if name == target_name:
            print(f"FOUND: {node.Path}")
            # Don't return, might be multiple
        
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
        
        print(f"Searching for 'PER_ERROR' in tree (max_depth=10)...")
        root = aspen.Tree.FindNode(r"\Data")
        find_node_by_name(root, "PER_ERROR", max_depth=10)
        
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
