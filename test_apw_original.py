import win32com.client as win32
import os
import time

def main():
    apw_path = os.path.abspath(r"Methanol Plant\MethanolPlant.apw")
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitFromArchive2(apw_path)
        aspen.Visible = 1
        aspen.SuppressDialogs = 1
        
        print(f"Original APW Loaded: {apw_path}")
        
        # Check flowsheet
        streams = aspen.Tree.FindNode(r"\Data\Streams")
        blocks = aspen.Tree.FindNode(r"\Data\Blocks")
        if streams and blocks:
            print(f"Streams: {streams.Elements.Count}, Blocks: {blocks.Elements.Count}")
        else:
            print("Nodes not found using standard path.")
            
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
