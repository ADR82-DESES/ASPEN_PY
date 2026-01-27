"""
RESEARCH: Testing Engine.ProcessInput
"""
import win32com.client as win32
import time

log = open("processinput_research_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS PROCESSINPUT RESEARCH")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(5)
    aspen.Visible = True
    
    engine = aspen.Engine
    
    log_print("\nTesting engine.ProcessInput('BLOCK B1 MIXER')...")
    try:
         # ProcessInput usually takes a string
         engine.ProcessInput("BLOCK B1 MIXER")
         log_print("  Call finished")
         time.sleep(3)
         if aspen.Tree.FindNode(r"\Data\Blocks\B1"):
              log_print("  [SUCCESS!!!] Block B1 created via Engine.ProcessInput!")
         else:
              log_print("  [FAILED] B1 not found")
    except Exception as e:
         log_print(f"  [FAIL] {e}")

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
