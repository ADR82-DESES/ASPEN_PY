import win32com.client as win32
import os
import time

def find_node_by_name(node, name, depth=0, max_depth=6):
    if depth > max_depth: return
    try:
        if name in node.Name:
            print(f"FOUND: {node.Path}")
        
        if hasattr(node, "Elements"):
            for i in range(node.Elements.Count):
                find_node_by_name(node.Elements.Item(i), name, depth+1, max_depth)
    except:
        pass

def main():
    inp_path = os.path.abspath(r"Methanol Plant\MethanolPlant.inp")
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitNew()
        aspen.Visible = 1
        
        print(f"Importing {inp_path}...")
        aspen.Import(inp_path)
        
        print("Waiting 5s...")
        time.sleep(5)
        
        print("Searching for 'Streams' or 'Blocks'...")
        find_node_by_name(aspen.Tree.FindNode(r"\Data"), "Streams")
        find_node_by_name(aspen.Tree.FindNode(r"\Data"), "Blocks")
        
        streams = aspen.Tree.FindNode(r"\Data\Streams")
        if streams:
            print(f"Streams Elements Count: {streams.Elements.Count}")
            
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
