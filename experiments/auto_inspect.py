"""
RESEARCH: Automatic Example Discovery and Inspection
Finding any available .bkp example and inspecting its blocks
"""
import win32com.client as win32
import os
import subprocess
import time

log = open("auto_inspect_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS AUTO INSPECTION")
log_print("="*70)

try:
    # Find a .bkp file
    log_print("Searching for any .bkp file in AspenTech directory...")
    search_dir = r"C:\Program Files\AspenTech"
    found_files = []
    
    for root, dirs, files in os.walk(search_dir):
        for file in files:
            if file.endswith(".bkp"):
                found_files.append(os.path.join(root, file))
                if len(found_files) > 5: break
        if len(found_files) > 5: break

    if not found_files:
        log_print("No .bkp files found")
    else:
        aspen = win32.Dispatch("Apwn.Document")
        
        for example_path in found_files:
            log_print(f"\n--- Testing: {example_path} ---")
            try:
                aspen.InitFromArchive2(example_path)
                time.sleep(3)
                
                blocks = aspen.Tree.FindNode(r"\Data\Blocks")
                if blocks and blocks.Elements.Count > 0:
                    log_print(f"Found {blocks.Elements.Count} blocks")
                    for i in range(min(5, blocks.Elements.Count)):
                        b = blocks.Elements.Item(i)
                        log_print(f"  Block: {b.Name}")
                        
                        # Inspect the block node to find its TYPE or MODEL
                        # Usually it's in \Data\Blocks\NAME\Input\TYPE
                        try:
                            # Try common locations for type info
                            type_paths = [
                                r"Input\TYPE",
                                r"TYPE",
                                r"Model"
                            ]
                            for tp in type_paths:
                                try:
                                    t_node = b.FindNode(tp)
                                    if t_node:
                                        log_print(f"    {tp}: {t_node.Value}")
                                except:
                                    pass
                        except:
                            pass
                    break # Success!
                else:
                    log_print("No blocks found in this simulation")
            except Exception as e:
                log_print(f"Error loading {example_path}: {e}")

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
