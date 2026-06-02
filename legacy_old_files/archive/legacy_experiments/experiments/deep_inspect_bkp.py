"""
RESEARCH: Absolute Block Inspection
Detailed inspection of an existing block to find its model string
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
    for i in range(blocks.Elements.Count):
        b = blocks.Elements.Item(i)
        print(f"\nBlock: {b.Name}")
        print(f"  Path: {b.Path}")
        
        # Test common type/model attributes
        for attr in ["Value", "Model", "ModelName", "Type", "ModelLibrary"]:
            try:
                val = getattr(b, attr)
                print(f"  {attr}: {val}")
            except:
                pass
        
        # Check sub-nodes
        try:
             # Often \Data\Blocks\B1\Input\TYPE exists
             for st in ["Input\\TYPE", "Input\\MODEL", "TYPE", "MODEL"]:
                  try:
                       n = b.FindNode(st)
                       if n:
                            print(f"  Node {st} value: {n.Value}")
                  except:
                       pass
        except:
             pass

if __name__ == "__main__":
    inspect()
