import win32com.client as win32
import os

def inspect_object(obj, name):
    print(f"\nInspecting {name}:")
    try:
        # We can't use dir() on COM objects easily, but we can try to access common methods
        methods = ["Import", "ImportSimulation", "InitNew", "InitFromFile2", "Open"]
        for m in methods:
            if hasattr(obj, m):
                print(f"  [OK] Has method: {m}")
            else:
                print(f"  [--] Missing: {m}")
    except Exception as e:
        print(f"Error inspecting {name}: {e}")

def main():
    try:
        aspen = win32.GetActiveObject("Apwn.Document")
    except:
        aspen = win32.Dispatch("Apwn.Document")
    
    inspect_object(aspen, "Document")
    if hasattr(aspen, "Engine"):
        inspect_object(aspen.Engine, "Engine")
    else:
        print("Engine object not found")

if __name__ == "__main__":
    main()
