import win32com.client as win32
import os
import time

def main():
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitNew()
        aspen.Visible = 1
        aspen.SuppressDialogs = 1
        
        print("Adding components...")
        # Simplest way to add components is via tree if possible, 
        # but usually it's easier to load a template.
        # For now, let's just see if we can add a block to a blank sim.
        
        blocks = aspen.Tree.FindNode(r"\Data\Blocks")
        print(f"Current blocks: {blocks.Elements.Count}")
        
        print("Attempting to add Mixer block 'M1'...")
        try:
            # Try adding with type as 2nd argument
            new_block = blocks.Elements.Add("M1", "Mixer")
            print(f"SUCCESS! Block added: {new_block.Path}")
        except Exception as e:
            print(f"Add('M1', 'Mixer') failed: {e}")
            
            print("Attempting to add block 'M2' then set type...")
            try:
                new_block = blocks.Elements.Add("M2")
                # Need to find the type node
                type_node = aspen.Tree.FindNode(r"\Data\Blocks\M2\Input\TYPE")
                if type_node:
                    type_node.Value = "Mixer"
                    print("SUCCESS! Type set for M2")
                else:
                    print("Type node not found for M2")
            except Exception as e2:
                print(f"Add('M2') + Set Type failed: {e2}")
                
        aspen.Quit()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
