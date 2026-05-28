"""
RESEARCH: Static Dispatch Exploration
"""
import win32com.client as win32
import sys

log = open("static_dispatch_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS STATIC DISPATCH RESEARCH")
log_print("="*70)

try:
    # This will try to generate a python module for the type library
    aspen = win32.gencache.EnsureDispatch("Apwn.Document")
    log_print(f"Static dispatch object: {aspen}")
    
    # Now check for all methods and properties (including hidden ones)
    log_print("\nEnumerating all methods/properties (static):")
    all_attrs = dir(aspen)
    log_print(f"Total attributes: {len(all_attrs)}")
    
    promising = [a for a in all_attrs if any(kw in a.lower() for kw in ['block', 'mixer', 'unit', 'op', 'lib', 'model'])]
    log_print(f"Promising attributes: {promising}")
    
    # Check constants
    # module = sys.modules[aspen.__module__]
    # log_print(f"Constants found in module: {dir(module.constants) if hasattr(module, 'constants') else 'None'}")

except Exception as e:
    log_print(f"Static dispatch error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
