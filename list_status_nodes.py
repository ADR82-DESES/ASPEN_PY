import win32com.client as win32
import os

def main():
    root_dir = r"C:\Users\domingueza\ASPEN_PY"
    apw_path = os.path.join(root_dir, "Methanol Plant", "MethanolPlant_ready.apw")
    
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitFromArchive2(apw_path)
        
        target_path = r"\Data\Results Summary\Run-Status\Output"
        print(f"Listing elements in: {target_path}")
        node = aspen.Tree.FindNode(target_path)
        
        if node and hasattr(node, "Elements"):
            print(f"Total elements: {node.Elements.Count}")
            for i in range(node.Elements.Count):
                try:
                    child = node.Elements.Item(i)
                    print(f"  {i}: {child.Name} = {child.Value}")
                except:
                    pass
        else:
            print("Node or Elements not found.")
            
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
