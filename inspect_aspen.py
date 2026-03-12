import win32com.client as win32
import os

def inspect():
    try:
        # Get active object if possible, or Dispatch
        aspen = win32.GetActiveObject("Apwn.Document")
        print("Connected to active Aspen instance.")
    except:
        print("No active instance found via GetActiveObject. Trying Dispatch...")
        aspen = win32.Dispatch("Apwn.Document")

    nodes = [
        r"\Data\Results Summary\Run-Status\Output\PER_ERROR",
        r"\Data\Results Summary\Run-Status\Output\MESSAGES",
        r"\Data\Results Summary\Flowsheet-Status\Output\STATUS_MSG",
    ]

    for path in nodes:
        try:
            node = aspen.Tree.FindNode(path)
            if node:
                print(f"Node {path}: {node.Value}")
            else:
                print(f"Node {path} NOT FOUND.")
        except Exception as e:
            print(f"Error reading {path}: {e}")

    # Also list any blocks with errors
    try:
        blocks_node = aspen.Tree.FindNode(r"\Data\Blocks")
        if blocks_node:
            for i in range(blocks_node.Elements.Count):
                block = blocks_node.Elements.Item(i)
                status_node = block.FindNode(r"Output\Status") # Path might vary
                if status_node:
                     print(f"Block {block.Name} Status: {status_node.Value}")
    except Exception as e:
        print(f"Error listing blocks: {e}")

if __name__ == "__main__":
    inspect()
