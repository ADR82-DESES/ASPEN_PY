"""
RESEARCH: TypeLib introspection
Reading the TypeLib to find the 'Add' signature
"""
import pythoncom
import win32com.client

def introspect_typelib():
    path = r"C:\Program Files\AspenTech\Aspen Plus V14.0\GUI\Xeq\x86\AspenPlus.tlb"
    try:
        tlib = pythoncom.LoadTypeLib(path)
        print(f"Loaded TypeLib: {tlib.GetLibAttr()}")
        
        for i in range(tlib.GetTypeInfoCount()):
            ti = tlib.GetTypeInfo(i)
            ta = ti.GetTypeAttr()
            name = tlib.GetDocumentation(i)[0]
            
            if "Elements" in name:
                print(f"\nTypeInfo {i}: {name} (GUID: {ta[0]})")
                # Look for 'Add' method
                for j in range(ta[7]): # cFuncs
                    fd = ti.GetFuncDesc(j)
                    fname = ti.GetNames(fd[0])[0]
                    if fname == "Add":
                        print(f"  Found Add method!")
                        print(f"    FuncDesc: {fd}")
                        # Get parameter names
                        names = ti.GetNames(fd[0])
                        print(f"    Names: {names}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    introspect_typelib()
