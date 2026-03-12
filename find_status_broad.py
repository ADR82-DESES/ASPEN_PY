import win32com.client as win32
import os

def search_for_node_pattern(node, pattern_list, depth=0, max_depth=6):
    if depth > max_depth: return
    try:
        for p in pattern_list:
            if p in node.Name:
                print(f"MATCH [{p}]: {node.Path}")
        
        if hasattr(node, "Elements"):
            for i in range(node.Elements.Count):
                search_for_node_pattern(node.Elements.Item(i), pattern_list, depth+1, max_depth)
    except:
        pass

def main():
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitFromArchive2(os.path.abspath(r"Methanol Plant\MethanolPlant_ready.apw"))
        
        root = aspen.Tree.FindNode(r"\Data")
        patterns = ["History", "Message", "Output", "Diagnostic", "Log"]
        print(f"Searching for patterns: {patterns}...")
        search_for_node_pattern(root, patterns)
        print("Done.")
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
