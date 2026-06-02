import win32com.client as win32
import os

def main():
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitNew()
        aspen.Visible = 1
        aspen.SuppressDialogs = 1
        
        print("Checking if we can add a stream...")
        streams_node = aspen.Tree.FindNode(r"\Data\Streams")
        if streams_node:
            s1 = streams_node.Elements.Add("S1")
            if s1:
                print("[OK] Successfully added stream S1 manually.")
                # Verify it's there
                node = aspen.Tree.FindNode(r"\Data\Streams\S1")
                if node:
                    print("[OK] Verified stream S1 in tree.")
                else:
                    print("[FAIL] Could not find stream S1 after adding.")
            else:
                print("[FAIL] Elements.Add('S1') returned None")
        else:
            print("[FAIL] Could not find \\Data\\Streams node")
            
        aspen.Quit()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
