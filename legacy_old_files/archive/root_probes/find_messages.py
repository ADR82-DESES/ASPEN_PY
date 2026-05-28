import win32com.client as win32
import os

def search_for_node(node, name, depth=0, max_depth=8):
    if depth > max_depth: return
    try:
        if name in node.Name:
            print(f"FOUND: {node.Path}")
        
        if hasattr(node, "Elements"):
            for i in range(node.Elements.Count):
                search_for_node(node.Elements.Item(i), name, depth+1, max_depth)
    except:
        pass

def main():
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitFromArchive2(os.path.abspath(r"Methanol Plant\MethanolPlant_ready.apw"))
        
        root = aspen.Tree.FindNode(r"\Data")
        print("Searching for 'MESSAGES'...")
        search_for_node(root, "MESSAGES")
        print("Done.")
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
