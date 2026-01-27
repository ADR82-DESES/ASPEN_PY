"""
RESEARCH: Testing Generate and CreateRouteTree
"""
import win32com.client as win32
import time

log = open("generate_research_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS GENERATE RESEARCH")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(5)
    
    # [1] Testing Generate
    log_print("\n[1] Testing Generate()...")
    try:
         res = aspen.Generate()
         log_print(f"  Result: {res}")
    except Exception as e:
         log_print(f"  Fail Generate: {e}")

    # [2] Testing CreateRouteTree
    log_print("\n[2] Testing CreateRouteTree()...")
    try:
         res = aspen.CreateRouteTree()
         log_print(f"  Result: {res}")
         if res:
              log_print(f"  Methods: {[m for m in dir(res) if not m.startswith('_')]}")
    except Exception as e:
         log_print(f"  Fail CreateRouteTree: {e}")

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
