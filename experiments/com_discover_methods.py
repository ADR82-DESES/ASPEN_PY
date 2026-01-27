import win32com.client as win32
import os

def discover():
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitNew() 
        
        objs = [('Document', aspen), ('Engine', aspen.Engine)]
        
        for name, obj in objs:
            print(f"\n--- {name} Methods ---")
            methods = [m for m in dir(obj) if not m.startswith('_')]
            for m in sorted(methods):
                if any(k in m.lower() for k in ['import', 'run', 'script', 'add', 'create', 'export']):
                    print(f"  [!] {m}")
                else:
                    print(f"  {m}")
                    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    discover()
