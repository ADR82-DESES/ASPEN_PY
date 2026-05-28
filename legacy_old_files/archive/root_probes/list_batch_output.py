import win32com.client as win32
import os

def main():
     try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitFromArchive2(os.path.abspath(r"Methanol Plant\MethanolPlant_ready.apw"))
        
        path = r"\Data\Convergence\Batch-Options\Output"
        node = aspen.Tree.FindNode(path)
        print(f"Nodes under {path} (Count: {node.Elements.Count}):")
        for i in range(node.Elements.Count):
            try:
                child = node.Elements.Item(i)
                print(f"  {i}: {child.Name} = {child.Value}")
            except: pass
            
        aspen.Quit()
     except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
