import win32com.client as win32
import os

def main():
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitNew()
        aspen.Visible = 1
        aspen.SuppressDialogs = 1
        
        print("Testing manual stream addition...")
        streams = aspen.Tree.FindNode(r"\Data\Streams")
        if streams:
            try:
                # Add a new stream
                new_stream = streams.Elements.Add("TEST_S1")
                print(f"[SUCCESS] Stream 'TEST_S1' added. Path: {new_stream.Path}")
                
                # Try to set a value
                temp_node = aspen.Tree.FindNode(r"\Data\Streams\TEST_S1\Input\TEMP\MIXED")
                if temp_node:
                    temp_node.Value = 25.0
                    print(f"[SUCCESS] Value set: {temp_node.Value}")
                else:
                    print("[FAIL] Could not find TEMP node for new stream.")
            except Exception as e:
                print(f"[FAIL] Error adding stream: {e}")
        else:
            print("[FAIL] \Data\Streams node not found in InitNew().")
            
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
