"""
RESEARCH: IHNode exploration
"""
import win32com.client as win32
import os
import time

def inspect():
    file_path = r"C:\Program Files\AspenTech\Aspen Plus V14.0\Favorites\testprob.bkp"
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitFromArchive2(os.path.abspath(file_path))
    aspen.Visible = True
    aspen.SuppressDialogs = 1
    
    time.sleep(10)
    
    blocks = aspen.Tree.FindNode(r"\Data\Blocks")
    if blocks.Elements.Count > 0:
        b = blocks.Elements.Item(0)
        print(f"Block object: {b}")
        print("Attributes:")
        for attr in sorted(dir(b)):
            if not attr.startswith("_"):
                print(f"  {attr}")
                
if __name__ == "__main__":
    inspect()
