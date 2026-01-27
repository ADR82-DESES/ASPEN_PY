"""
DEBUG: Simple Connection Test
"""
import win32com.client as win32

try:
    print("Dispatching Apwn.Document...")
    aspen = win32.Dispatch("Apwn.Document")
    print("Dispatch successful.")
    
    print(f"Aspen Name: {aspen.Name}")
    print(f"Aspen FullName: {aspen.FullName}")
    
    # Check if a document is already open
    try:
        if aspen.Tree:
            print("A tree is already present.")
    except:
        print("No tree present yet.")

except Exception as e:
    print(f"Error: {e}")
