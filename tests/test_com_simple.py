import win32com.client as win32
import sys

print("Testing win32com.client.Dispatch('Apwn.Document')...")
try:
    aspen = win32.Dispatch("Apwn.Document")
    print(f"Success! Object type: {type(aspen)}")
    print("Trying to call InitNew()...")
    aspen.InitNew()
    print("Success!")
    aspen.Quit()
except Exception as e:
    print(f"Failed: {e}")
    sys.exit(1)
