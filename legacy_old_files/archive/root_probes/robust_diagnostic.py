import win32com.client as win32
import os
import time

def find_status_node(node, depth=0, max_depth=10):
    if depth > max_depth: return None
    try:
        if "PER_ERROR" in node.Name: return node
        if hasattr(node, "Elements"):
            for i in range(node.Elements.Count):
                found = find_status_node(node.Elements.Item(i), depth+1, max_depth)
                if found: return found
    except: pass
    return None

def main():
    root_dir = r"C:\Users\domingueza\ASPEN_PY"
    apw_path = os.path.join(root_dir, "Methanol Plant", "MethanolPlant.apw")
    out_path = os.path.join(root_dir, "aspen_diagnostic_out.txt")
    
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitFromArchive2(apw_path)
        aspen.Visible = 1
        aspen.SuppressDialogs = 1
        
        print(f"Running: {apw_path}")
        aspen.Reinit()
        aspen.Engine.Run2(1)
        
        start = time.time()
        while aspen.Engine.IsRunning and time.time() - start < 30:
            time.sleep(1)
        
        print("Capturing data...")
        with open(out_path, "w") as f:
            f.write(f"Simulation: {apw_path}\n")
            f.write(f"Timestamp: {time.ctime()}\n\n")
            
            # 1. Try to find PER_ERROR anywhere
            status_node = find_status_node(aspen.Tree.FindNode(r"\Data"), max_depth=8)
            if status_node:
                f.write(f"Status Node Path: {status_node.Path}\n")
                f.write(f"Status Value: {status_node.Value}\n\n")
            else:
                f.write("Status Node (PER_ERROR) not found.\n\n")
            
            # 2. Capture all messages
            msg_node = aspen.Tree.FindNode(r"\Data\Results Summary\Run-Status\Output\MESSAGES")
            if msg_node:
                f.write("--- MESSAGES ---\n")
                f.write(str(msg_node.Value))
            else:
                f.write("MESSAGES node not found.\n")
                
        print(f"Diagnostics saved to {out_path}")
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
