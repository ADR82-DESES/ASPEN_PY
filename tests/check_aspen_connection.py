import win32com.client as win32
import os

def check_aspen():
    print("Checking Aspen Plus COM interface...")
    try:
        aspen = win32.Dispatch("Apwn.Document")
        print("Successfully dispatched Apwn.Document")
        print(f"Aspen Version: {aspen.Version}")
        # Initialize a new one to unlock the tree
        aspen.InitNew()
        print("Successfully initialized new document")
        aspen.Close()
        print("Closed Aspen")
        return True
    except Exception as e:
        print(f"Failed to connect to Aspen Plus: {e}")
        return False

if __name__ == "__main__":
    check_aspen()
