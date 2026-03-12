import win32com.client as win32
import os

def main():
    apw_path = os.path.abspath(r"Methanol Plant\MethanolPlant_ready.apw")
    export_path = os.path.abspath(r"Methanol Plant\exported_syntax.inp")
    
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitFromArchive2(apw_path)
        aspen.Visible = 1
        aspen.SuppressDialogs = 1
        
        print(f"Exporting to {export_path}...")
        # Type 4 is usually Input file
        aspen.Export(4, export_path)
        print("Export successful!")
        
        aspen.Quit()
        
        if os.path.exists(export_path):
            with open(export_path, 'r') as f:
                content = f.read(1000) # Read first 1000 chars
                print("\n--- Exported Syntax (First 1000 chars) ---")
                print(content)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
