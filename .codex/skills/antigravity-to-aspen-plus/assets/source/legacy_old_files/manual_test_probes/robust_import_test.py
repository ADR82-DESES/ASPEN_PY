"""
RESEARCH: Absolute Block Creation via Import
Creating a small .inp file and importing it
"""
import win32com.client as win32
import os
import time

def test_import():
    # 1. Start Aspen
    aspen = win32.Dispatch("Apwn.Document")
    # We MUST initialize first, but maybe InitNew is hanging.
    # Let's try to load an existing empty-ish template or file.
    template_path = r"C:\Program Files\AspenTech\Aspen Plus V14.0\Favorites\testprob.bkp"
    aspen.InitFromArchive2(os.path.abspath(template_path))
    aspen.Visible = True
    aspen.SuppressDialogs = 1
    time.sleep(10)

    # 2. Create Import File
    inp_content = """
BLOCK MIXER B_IMP
"""
    inp_path = os.path.abspath("import_test.inp")
    with open(inp_path, "w") as f:
        f.write(inp_content)

    print(f"Attempting to import {inp_path}...")
    try:
        # In modern versions, Import might be on the Document or Engine
        # Documentation says Document.Import(filename)
        aspen.Import(inp_path)
        print("Import call finished.")
        time.sleep(5)

        # Check if B_IMP exists
        node = aspen.Tree.FindNode(r"\Data\Blocks\B_IMP")
        if node:
            print("SUCCESS! Block B_IMP created via Import.")
        else:
            print("FAIL: Block B_IMP not found after import.")
    except Exception as e:
        print(f"Error during import: {e}")

if __name__ == "__main__":
    test_import()
