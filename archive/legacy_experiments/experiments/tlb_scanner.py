"""
RESEARCH: TypeLib search through all TLBs
"""
import pythoncom
import os

def find_apwn_tlb():
    search_root = r"C:\Program Files\AspenTech"
    for root, dirs, files in os.walk(search_root):
        for file in files:
            if file.lower().endswith(".tlb"):
                path = os.path.join(root, file)
                try:
                    tlib = pythoncom.LoadTypeLib(path)
                    for i in range(tlib.GetTypeInfoCount()):
                        name = tlib.GetDocumentation(i)[0]
                        if name == "Apwn.Document" or name == "IHNode" or name == "IHEAPwn":
                            print(f"FOUND MATCH: {name} in {path}")
                            return path
                except:
                    pass
    return None

if __name__ == "__main__":
    tlb = find_apwn_tlb()
    if tlb:
        print(f"Main Aspen Plus TLB: {tlb}")
    else:
        print("Main TLB not found via scanning.")
