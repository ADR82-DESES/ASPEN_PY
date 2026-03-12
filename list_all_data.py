import win32com.client as win32
import os

def main():
     try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitFromArchive2(os.path.abspath(r"Methanol Plant\MethanolPlant_ready.apw"))
        
        root = aspen.Tree.FindNode(r"\Data")
        print(f"Nodes under \\Data (Count: {root.Elements.Count}):")
        for i in range(root.Elements.Count):
            try:
                child = root.Elements.Item(i)
                print(f"  {i}: {child.Name}")
            except: pass
            
        print("\nNodes under \\Data\\Results Summary (Count: {aspen.Tree.FindNode(r'\Data\Results Summary').Elements.Count}):")
        rs = aspen.Tree.FindNode(r"\Data\Results Summary")
        for i in range(rs.Elements.Count):
            try:
                child = rs.Elements.Item(i)
                print(f"  {i}: {child.Name}")
            except: pass
            
        aspen.Quit()
     except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
