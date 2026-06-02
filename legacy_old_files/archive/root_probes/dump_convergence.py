import win32com.client as win32
import os

def dump_node(aspen, path, max_depth=3):
    print(f"\nDumping {path}:")
    node = aspen.Tree.FindNode(path)
    if not node:
        print("  NOT FOUND")
        return
    
    def walk(n, d):
        if d > max_depth: return
        try:
            val = n.Value
            print(f"{'  '*d}{n.Name} = {val}")
            if hasattr(n, "Elements"):
                for i in range(n.Elements.Count):
                    walk(n.Elements.Item(i), d+1)
        except: pass

    walk(node, 0)

def main():
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitFromArchive2(os.path.abspath(r"Methanol Plant\MethanolPlant_ready.apw"))
        
        dump_node(aspen, r"\Data\Results Summary\Conv-Sum")
        dump_node(aspen, r"\Data\Convergence")
        
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
