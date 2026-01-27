import pythoncom
import win32com.client

print("Scanning Running Object Table (ROT)...")
try:
    context = pythoncom.CreateBindCtx(0)
    rot = pythoncom.GetRunningObjectTable()
    enum = rot.EnumRunning()
    
    found = False
    while True:
        monikers = enum.Next()
        if not monikers: break
        
        for moniker in monikers:
            try:
                name = moniker.GetDisplayName(context, None)
                if "Aspen" in name or "Apwn" in name or ".bkp" in name or ".apw" in name:
                    print(f"  FOUND CANDIDATE: {name}")
                    found = True
                    # Try to bind?
                    # obj = rot.GetObject(moniker)
            except:
                pass
                
    if not found:
        print("  No obvious Aspen objects found in ROT.")
        print("  Possible reasons: Admin mismatch, or specific simulation file not open.")
    else:
        print("  Scan complete.")

except Exception as e:
    print(f"Error scanning ROT: {e}")
