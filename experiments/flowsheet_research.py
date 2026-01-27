"""
RESEARCH: Exploring Flowsheet Node
"""
import win32com.client as win32
import time

log = open("flowsheet_research_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS FLOWSHEET RESEARCH")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(5)
    
    flowsheet = aspen.Tree.FindNode(r"\Data\Flowsheet")
    if flowsheet:
         log_print(f"Flowsheet node: {flowsheet}")
         # Explore children
         if hasattr(flowsheet, 'Elements'):
              log_print(f"Flowsheet Elements count: {flowsheet.Elements.Count}")
              for i in range(flowsheet.Elements.Count):
                   log_print(f"  Item({i}): {flowsheet.Elements.Item(i).Name}")
    else:
         log_print("Flowsheet node not found")

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
