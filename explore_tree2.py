import os
import sys
import win32com.client as win32

filepath = r"c:\Users\domingueza\ASPEN_PY\Methanol Plant\MethanolPlant.apw"

print(f"Loading {filepath}...")
aspen = win32.Dispatch('Apwn.Document')
aspen.InitFromArchive2(os.path.abspath(filepath))

def print_tree(node, depth=0):
    if depth > 4: return
    if node is None: return
    print("  "*depth + str(node.Name))
    if hasattr(node, 'Elements'):
        try:
            for elem in node.Elements:
                print_tree(elem, depth + 1)
        except Exception:
            pass

rs_node = aspen.Tree.FindNode(r"\Data\Results Summary")
if rs_node:
    print("Nodes under Results Summary:")
    print_tree(rs_node)
else:
    print("Could not find Results Summary node")

sys.exit(0)
