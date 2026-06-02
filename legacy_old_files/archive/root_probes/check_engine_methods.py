import win32com.client as win32
import os

def main():
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitNew()
        print("Checking aspen.Engine for ImportInput...")
        if hasattr(aspen.Engine, "ImportInput"):
            print("[OK] Engine has ImportInput")
        else:
            print("[FAIL] Engine does NOT have ImportInput")
        
        # Check other candidates
        candidates = ["Import", "ImportSimulation", "LoadInput", "ParseInput"]
        for c in candidates:
            if hasattr(aspen.Engine, f"{c}"):
                print(f"[OK] Engine has {c}")
                
        # Check Document candidates
        print("Checking aspen document for other import candidates...")
        for c in ["ImportInput", "ImportSimulation"]:
            if hasattr(aspen, f"{c}"):
                print(f"[OK] Document has {c}")

        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
