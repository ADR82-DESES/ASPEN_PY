import win32com.client as win32
import os

def dump_tree(node, depth=0, max_depth=4):
    if depth > max_depth:
        return
    try:
        name = node.Name
        try:
            val = node.Value
        except:
            val = "<no value>"
        print(f"{'  ' * depth}{name} = {val}")
        
        if hasattr(node, "Elements"):
            for i in range(node.Elements.Count):
                dump_tree(node.Elements.Item(i), depth + 1, max_depth)
    except:
        pass

def main():
    apw_path = os.path.abspath(r"Methanol Plant\MethanolPlant_ready.apw")
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitFromArchive2(apw_path)
        aspen.Visible = 1
        aspen.SuppressDialogs = 1
        
        # Run it to get results
        aspen.Reinit()
        aspen.Engine.Run2(1)
        while aspen.Engine.IsRunning:
            import time
            time.sleep(1)
            
        print("\n--- Results Summary Tree ---")
        root = aspen.Tree.FindNode(r"\Data\Results Summary")
        if root:
            dump_tree(root)
        else:
            print("Could not find \\Data\\Results Summary")
            
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
