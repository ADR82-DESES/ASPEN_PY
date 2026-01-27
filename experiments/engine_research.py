"""
RESEARCH: Aspen Engine Methods
Checking methods on the Engine object
"""
import win32com.client as win32
import time

log = open("engine_research_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS ENGINE RESEARCH")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(5)
    
    engine = aspen.Engine
    log_print(f"Engine object: {engine}")
    
    methods = [m for m in dir(engine) if not m.startswith('_')]
    log_print(f"Engine methods: {methods}")
    
    # Try RunScript on Engine
    if 'RunScript' in methods:
         log_print("\nTesting engine.RunScript('BLOCK B1 MIXER')...")
         try:
              engine.RunScript("BLOCK B1 MIXER")
              log_print("  Call finished")
              time.sleep(2)
              if aspen.Tree.FindNode(r"\Data\Blocks\B1"):
                   log_print("  [VERIFIED] Block B1 created via Engine.RunScript!")
         except Exception as e:
              log_print(f"  [FAIL] {e}")

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
