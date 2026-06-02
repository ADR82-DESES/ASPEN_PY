"""
DEBUG: InitNew Progress Tracker
"""
import win32com.client as win32
import time

def log(msg):
    with open("init_status.txt", "a") as f:
        f.write(f"{time.ctime()}: {msg}\n")
    print(msg)

log("Starting test...")
try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.Visible = True
    aspen.SuppressDialogs = 1
    log("Dispatch and setup done.")
    
    log("Calling InitNew()...")
    # Wrap in a try-except because it might take a long time
    aspen.InitNew()
    log("InitNew() returned.")
    
    time.sleep(5)
    log(f"Document Name: {aspen.Name}")
    
    blocks = aspen.Tree.FindNode(r"\Data\Blocks")
    if blocks:
        log("Found Blocks node.")
    else:
        log("Blocks node NOT found.")

except Exception as e:
    log(f"Error: {e}")
