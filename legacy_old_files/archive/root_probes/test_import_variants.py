import win32com.client as win32
import os
import time

def check_tree(aspen):
    try:
        # Check for components or streams
        node = aspen.Tree.FindNode(r"\Data\Streams")
        if node and node.Elements.Count > 0:
            print(f"  [SUCCESS] Tree populated with {node.Elements.Count} streams!")
            return True
        else:
            print("  [FAIL] Tree still empty.")
            return False
    except Exception as e:
        print(f"  [ERROR] Error checking tree: {e}")
        return False

def main():
    path = os.path.abspath("Methanol_Session_Minimal/temp_simulation.inp")
    if not os.path.exists(path):
        print(f"INP missing at {path}")
        return

    print(f"Testing Import variants for {path}...")
    
    # We'll use a single Aspen instance
    aspen = win32.Dispatch("Apwn.Document")
    
    # CRITICAL: InitNew FIRST, THEN set properties
    aspen.InitNew()
    aspen.Visible = 1
    aspen.SuppressDialogs = 1

    def test_variant(name, func):
        print(f"\nVariant: {name}")
        try:
            # Re-init for each test to ensure clean state
            aspen.InitNew()
            # Reset props just in case InitNew cleared them
            aspen.Visible = 1
            aspen.SuppressDialogs = 1
            
            func(aspen, path)
            time.sleep(2) # Give it time to parse
            print("  Command finished without exception.")
            if check_tree(aspen):
                print(f"  !!! {name} WORKED !!!")
                return True
        except Exception as e:
            print(f"  [ERROR] {e}")
        return False

    variants = [
        ("Import(4, path)", lambda a, p: a.Import(4, p)),
        ("Import(path, 4)", lambda a, p: a.Import(p, 4)),
        ("Import(path)", lambda a, p: a.Import(p)),
        ("InitFromFile2(path)", lambda a, p: a.InitFromFile2(p)),
    ]

    working_variant = None
    for name, func in variants:
        if test_variant(name, func):
            working_variant = name
            break
    
    if working_variant:
        print(f"\nFOUND WORKING VARIANT: {working_variant}")
    else:
        print("\nNO VARIANT WORKED")
    
    aspen.Quit()

if __name__ == "__main__":
    main()
