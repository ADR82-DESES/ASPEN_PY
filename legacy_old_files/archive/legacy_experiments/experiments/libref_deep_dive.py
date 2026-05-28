"""
RESEARCH: LibRef Deep Dive
Enumerating libraries and searching for Mixer models
"""
import win32com.client as win32
import time

log = open("libref_deep_dive_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS LIBREF DEEP DIVE")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(5)
    
    libref = aspen.LibRef
    log_print(f"LibRef object: {libref}")
    
    # [1] Count libraries
    try:
        count = libref.CountLibs
        log_print(f"Number of libraries found: {count}")
    except Exception as e:
        log_print(f"CountLibs error: {e}")
        count = 0

    # [2] Enumerate libraries
    log_print("\n[2] Enumerating Libraries...")
    for i in range(count):
        try:
            name = libref.LibraryName(i)
            path = libref.LibraryPath(i)
            log_print(f"  Library {i}: {name} | Path: {path}")
            
            # See if we can "Select" or "Activate" it if it's not
            # libref.SetLibraryActive(i, True)
        except Exception as e:
            log_print(f"  Error at index {i}: {e}")

    # [3] Search for Categories
    log_print("\n[3] Enumerating Categories...")
    # Based on methods: CategoryName, CategorySelected
    # We might need to know how many categories there are.
    # Let's try to find a count for categories.
    
    # [4] Testing InsertLibrary if we can find where Mixer lives
    # Usually it's in a .DLL or .AP library file
    
    # Let's try to search the tree under \Data for any Library reference nodes
    log_print("\n[4] Searching Data tree for Libraries...")
    def search_libs(node, depth=0):
        if depth > 4: return
        try:
            if "Library" in node.Name:
                log_print(f"  {'  '*depth}Found: {node.Name} | Path: {node.Path}")
            if hasattr(node, 'Elements'):
                for i in range(node.Elements.Count):
                    search_libs(node.Elements.Item(i), depth + 1)
        except:
            pass
            
    search_libs(aspen.Tree.FindNode(r"\Data"))

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
