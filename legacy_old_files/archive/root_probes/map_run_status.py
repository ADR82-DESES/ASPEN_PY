import win32com.client as win32
import os

def dump_tree_recursive(node, max_depth=3, current_depth=0):
    if current_depth > max_depth:
        return
    
    prefix = "  " * current_depth
    try:
        name = node.Name
        # Try to get value if it's a leaf
        val = None
        try:
            val = node.Value
        except:
            pass
        
        print(f"{prefix}{name} = {val}")
        
        if hasattr(node, "Elements"):
            for i in range(node.Elements.Count):
                dump_tree_recursive(node.Elements.Item(i), max_depth, current_depth + 1)
    except Exception as e:
        # print(f"{prefix}[Error] {e}")
        pass

def main():
    try:
        aspen = win32.GetActiveObject("Apwn.Document")
    except:
        print("Could not attach to Aspen.")
        return

    print("Mapping nodes under \\Data\\Results Summary\\Run-Status...")
    root_node = aspen.Tree.FindNode(r"\Data\Results Summary\Run-Status")
    if root_node:
        dump_tree_recursive(root_node)
    else:
        print("Could not find \\Data\\Results Summary\\Run-Status")

if __name__ == "__main__":
    main()
