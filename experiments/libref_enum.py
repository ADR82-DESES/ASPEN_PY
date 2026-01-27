"""
RESEARCH: LibRef Enumeration and Category exploration
"""
import win32com.client as win32
import time

log = open("libref_enum_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS LIBREF ENUMERATION")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(5)
    
    libref = aspen.LibRef
    
    log_print(f"Library name (0): {libref.LibraryName(0)}")
    
    # [1] Testing libref.Enum()
    log_print("\n[1] Testing libref.Enum(0)...")
    try:
        res = libref.Enum(0)
        log_print(f"  Result of Enum(0): {res}")
        if res:
             methods = [m for m in dir(res) if not m.startswith('_')]
             log_print(f"  Methods: {methods[:20]}")
    except Exception as e:
        log_print(f"  Enum(0) error: {e}")

    # [2] Enumerating Categories
    log_print("\n[2] Enumerating Categories (brute force search)...")
    for i in range(100):
        try:
            name = libref.CategoryName(i)
            if name:
                log_print(f"  Category {i}: {name}")
                # See if selected
                sel = libref.CategorySelected(i)
                log_print(f"    Selected: {sel}")
        except:
            # Reached end of categories
            if i > 5: break

    # [3] Searching for Model Names in LibRef
    # Maybe LibraryName(i) where i > 0 returns models?
    # Or maybe there's a ModelName(i) method?
    log_print("\n[3] Searching for Model methods...")
    methods = [m for m in dir(libref) if not m.startswith('_')]
    model_methods = [m for m in methods if 'model' in m.lower()]
    log_print(f"  Model-related methods: {model_methods}")

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
