import win32com.client as win32
import os
import time

def main():
    apw_path = os.path.abspath(r"Methanol Plant\MethanolPlant$backup.apw")
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitFromArchive2(apw_path)
        aspen.Visible = 1
        aspen.SuppressDialogs = 1
        
        print(f"Backup APW Loaded: {apw_path}")
        
        # Check flowsheet
        streams = aspen.Tree.FindNode(r"\Data\Streams")
        blocks = aspen.Tree.FindNode(r"\Data\Blocks")
        print(f"Streams: {streams.Elements.Count}, Blocks: {blocks.Elements.Count}")
        
        if streams.Elements.Count > 0 and blocks.Elements.Count > 0:
            print("[SUCCESS] Found a working flowsheet in the backup!")
            print("Verifying one key block...")
            atr = aspen.Tree.FindNode(r"\Data\Blocks\B-ATR")
            if atr:
                 print(f"Block B-ATR found at: {atr.Path}")
            
            # Check for PER_ERROR node to confirm convergeability
            per_error = aspen.Tree.FindNode(r"\Data\Convergence\Batch-Options\Output\PER_ERROR")
            if per_error:
                 print(f"Convergence node found: {per_error.Path}")
        else:
            print("[FAIL] Backup flowsheet is also empty.")
            
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
