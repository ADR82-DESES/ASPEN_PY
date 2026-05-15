"""
RESEARCH: Library Reference and Internal Models
Investigating LibRef, Application.RootModel, and hidden library collections
"""
import win32com.client as win32
import time
import pythoncom

log = open("internal_model_research_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS INTERNAL MODEL RESEARCH")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(5)
    aspen.Visible = True
    
    # [1] Investigating LibRef
    log_print("\n[1] Testing LibRef...")
    try:
        # Check if LibRef is a property or method
        res = aspen.LibRef
        log_print(f"  LibRef value: {res}")
        if hasattr(res, 'Elements'):
             log_print(f"  LibRef has {res.Elements.Count} elements")
             for i in range(min(5, res.Elements.Count)):
                  log_print(f"    - {res.Elements.Item(i).Name}")
    except Exception as e:
        log_print(f"  LibRef error: {e}")

    # [2] Investigating Application.RootModel
    log_print("\n[2] Testing RootModel...")
    try:
        root = aspen.Application.RootModel
        log_print(f"  RootModel: {root}")
        # Explore RootModel
        methods = [m for m in dir(root) if not m.startswith('_')]
        log_print(f"  RootModel methods: {methods[:20]}")
        
        # Check for child models or libraries
        for attr in ['ModelLibraries', 'Libraries', 'Models', 'Blocks']:
            try:
                val = getattr(root, attr)
                log_print(f"  Found {attr}: {val}")
                if hasattr(val, 'Count'):
                     log_print(f"    Count: {val.Count}")
            except:
                pass
    except Exception as e:
        log_print(f"  RootModel error: {e}")

    # [3] Searching for Model Palette equivalent
    log_print("\n[3] Searching for Palette/Model sources...")
    # Some older docs mention a 'Catalog' or 'Library'
    try:
        # Try to find where models are stored in the tree if they are
        # search for any node named 'Models'
        def find_models_node(node, depth=0):
            if depth > 3: return None
            try:
                if "Model" in node.Name:
                    return node
                if hasattr(node, 'Elements'):
                    for i in range(node.Elements.Count):
                        found = find_models_node(node.Elements.Item(i), depth + 1)
                        if found: return found
            except:
                pass
            return None

        found_node = find_models_node(aspen.Tree.FindNode(r"\Data"))
        if found_node:
            log_print(f"  Found potential models node: {found_node.Path}")
    except:
        pass

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
