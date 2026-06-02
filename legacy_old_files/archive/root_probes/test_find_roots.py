import win32com.client as win32
import os
import time

def find_node_by_name(node, name, depth=0, max_depth=8):
    if depth > max_depth: return
    try:
        if name.lower() in node.Name.lower():
            print(f"FOUND {name} at: {node.Path}")
        
        if hasattr(node, "Elements"):
            for i in range(node.Elements.Count):
                find_node_by_name(node.Elements.Item(i), name, depth+1, max_depth)
    except:
        pass

def main():
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitNew()
        aspen.Visible = 1
        
        print("Searching for 'Blocks'...")
        find_node_by_name(aspen.Tree.FindNode(r"\Data"), "Blocks")
        
        print("Searching for 'Streams'...")
        find_node_by_name(aspen.Tree.FindNode(r"\Data"), "Streams")
        
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
