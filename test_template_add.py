import win32com.client as win32
import os
import time

def main():
    template_path = r"C:\Program Files\AspenTech\Aspen Plus V14.0\GUI\Templates\BlankSimulation.apt"
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitFromArchive2(template_path)
        aspen.Visible = 1
        aspen.SuppressDialogs = 1
        
        print(f"Template loaded: {template_path}")
        
        blocks = aspen.Tree.FindNode(r"\Data\Blocks")
        print(f"Current blocks: {blocks.Elements.Count}")
        
        print("Attempting to add Mixer block 'M1'...")
        try:
            # Type as 2nd argument
            new_block = blocks.Elements.Add("M1", "Mixer")
            print(f"SUCCESS! Block added: {new_block.Path}")
            
            # Try to set a property to confirm it's alive
            type_node = aspen.Tree.FindNode(r"\Data\Blocks\M1\Input\TYPE")
            if type_node:
                print(f"Block TYPE is: {type_node.Value}")
        except Exception as e:
            print(f"Add('M1', 'Mixer') failed: {e}")
                
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
