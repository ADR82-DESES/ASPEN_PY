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
        
        print(f"Running simulation: {apw_path}")
        aspen.Reinit()
        aspen.Engine.Run2(1)
        
        start_time = time.time()
        while aspen.Engine.IsRunning:
            if time.time() - start_time > 60:
                print("Timeout waiting for run.")
                aspen.Engine.Stop()
                break
            time.sleep(1)
            
        print("Run finished. Checking status...")
        
        # Capture messages
        msg_node = aspen.Tree.FindNode(r"\Data\Results Summary\Run-Status\Output\MESSAGES")
        if msg_node:
            with open("aspen_messages.txt", "w") as f:
                f.write(str(msg_node.Value))
            print("Messages saved to aspen_messages.txt")
            
        # Check convergence
        for path in [r"\Data\Results Summary\Run-Status\Output\PER_ERROR", 
                     r"\Data\Convergence\Sequence\Batch-Options\Output\PER_ERROR"]:
            node = aspen.Tree.FindNode(path)
            if node:
                print(f"Status at {path}: {node.Value}")
                
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
