import win32com.client as win32
import os

def dump_node(node, indent=0):
    try:
        prefix = "  " * indent
        val = node.Value
        name = node.Name if hasattr(node, "Name") else "?"
        print(f"{prefix}{name} = {val}")
        
        # Recurse children
        if hasattr(node, "Elements"):
            for i in range(node.Elements.Count):
                dump_node(node.Elements.Item(i), indent + 1)
    except:
        pass

def inspect():
    try:
        aspen = win32.GetActiveObject("Apwn.Document")
    except:
        aspen = win32.Dispatch("Apwn.Document")

    paths = [
        r"\Data\Results Summary\Run-Status\Output",
        r"\Data\Results Summary\Flowsheet-Status\Output"
    ]

    for p in paths:
        print(f"\nDumping {p}:")
        try:
            node = aspen.Tree.FindNode(p)
            if node:
                dump_node(node)
            else:
                print("NOT FOUND")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    inspect()
