import win32com.client as win32
import os
import time

def main():
    apw_path = os.path.abspath(r"Methanol Plant\MethanolPlant_ready.apw")
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitFromArchive2(apw_path)
        aspen.Visible = 1
        aspen.SuppressDialogs = 1
        
        print(f"APW Loaded: {apw_path}")
        
        # Check flowsheet
        streams = aspen.Tree.FindNode(r"\Data\Streams")
        blocks = aspen.Tree.FindNode(r"\Data\Blocks")
        print(f"Streams: {streams.Elements.Count}, Blocks: {blocks.Elements.Count}")
        
        if streams.Elements.Count > 0 and blocks.Elements.Count > 0:
            print("Running simulation...")
            aspen.Reinit()
            aspen.Run() 
            
            # Wait for completion - using a more robust way to check running status
            start = time.time()
            # In V14, it seems IsRunning or Engine.IsRunning or Application.EngineRunning
            while True:
                is_running = False
                try: is_running = aspen.EngineRunning
                except: pass
                
                if not is_running: break
                
                elapsed = time.time() - start
                if elapsed > 120: 
                    print("Timeout!")
                    break
                
                if int(elapsed) % 10 == 0:
                    print(f"  Running... ({int(elapsed)}s)")
                time.sleep(2)
            
            print("Run finished. Checking conversion results...")
            # Check results of ATR block if possible
            atr_res = aspen.Tree.FindNode(r"\Data\Blocks\B-ATR\Output\BLKSTAT")
            if atr_res:
                print(f"B-ATR Status: {atr_res.Value}")
            
            # Check convergence node
            # V14 path discovered earlier: \Data\Convergence\Batch-Options\Output\PER_ERROR
            per_error = aspen.Tree.FindNode(r"\Data\Convergence\Batch-Options\Output\PER_ERROR")
            if per_error:
                print(f"Global Convergence (PER_ERROR): {per_error.Value}")
            else:
                # Try fallback V10 path
                per_error = aspen.Tree.FindNode(r"\Data\Results Summary\Run-Status\Output\PER_ERROR")
                if per_error:
                    print(f"Global Convergence (V10 path): {per_error.Value}")
        else:
            print("[FAIL] Flowsheet is empty in this APW.")
            
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
