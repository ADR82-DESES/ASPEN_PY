import win32com.client as win32
import time

def brute_force_mixer():
    print("Connecting...")
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    aspen.Visible = True
    
    blocks = aspen.Tree.FindNode(r"\Data\Blocks")
    
    names_to_try = [
        "Mixer", "Mixers", "MIXER", "MIXERS", "MIX", "Mix",
        "Model Library\Mixers\Mixer", "Model Library.Mixers.Mixer",
        "Built-In.Mixer", "User Models.Mixer",
        "B-MIXER", "Mixer/Splitter", "Mixer-Splitter"
    ]
    
    for name in names_to_try:
        print(f"Trying Add('B1', '{name}')...")
        try:
            blocks.Elements.Add("B1", name)
            print(f"  [SUCCESS] Worked with name: {name}")
            break
        except Exception as e:
            # print(f"  [FAIL] {str(e)[:50]}")
            pass

    # Check if B1 exists
    mixer = aspen.Tree.FindNode(r"\Data\Blocks\B1")
    if mixer:
        print("MIXER B1 created successfully!")
    else:
        print("Failed to create MIXER B1.")

if __name__ == "__main__":
    brute_force_mixer()
