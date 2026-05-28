import win32com.client as win32
try:
    aspen = win32.Dispatch("Apwn.Document")
    print(aspen.FullName)
except Exception as e:
    print(f"Error: {e}")
