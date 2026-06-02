import win32com.client as win32
import os

def main():
    apw_path = os.path.abspath(r"Methanol Plant\MethanolPlant_ready.apw")
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitFromArchive2(apw_path)
        
        print("\n--- root \\Data node children ---")
        root = aspen.Tree.FindNode(r"\Data")
        if root:
            for i in range(root.Elements.Count):
                try:
                    print(f"  {root.Elements.Item(i).Name}")
                except:
                    pass
        else:
            print("Could not find \\Data")
        
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
