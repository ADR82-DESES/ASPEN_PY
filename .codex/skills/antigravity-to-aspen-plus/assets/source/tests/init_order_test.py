"""
DEBUG: InitNew Order Test
"""
import win32com.client as win32
import time

def log(msg):
    print(f"{time.ctime()}: {msg}")

log("Starting test (Order 2)...")
try:
    aspen = win32.Dispatch("Apwn.Document")
    log("Dispatch successful.")

    log("Calling InitNew()...")
    aspen.InitNew()
    log("InitNew() returned successfully!")

    log("Setting properties...")
    aspen.Visible = True
    aspen.SuppressDialogs = 1
    log("Properties set.")

    time.sleep(2)
    print(f"Doc Name: {aspen.Name}")

except Exception as e:
    log(f"Error: {e}")
