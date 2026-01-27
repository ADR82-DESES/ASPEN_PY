"""
RESEARCH: Application Methods and Command Execution
Listing all methods on the Application object and testing command/script execution
"""
import win32com.client as win32
import sys

log = open("command_research_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS COMMAND RESEARCH")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    aspen.Visible = True
    
    app = aspen.Application
    log_print(f"Application object: {app}")
    
    # List all methods/properties of Application
    methods = [m for m in dir(app) if not m.startswith('_')]
    log_print(f"\n[1] Application Methods ({len(methods)}):")
    for i in range(0, len(methods), 5):
        log_print(f"  {', '.join(methods[i:i+5])}")

    # Search for execution methods
    exec_methods = [m for m in methods if any(kw in m.lower() for kw in ['execute', 'run', 'script', 'command', 'insert'])]
    log_print(f"\n[2] Execution Methods: {exec_methods}")

    # Test Command Execution if any method found
    command_str = "INSERT BLOCK B1 Mixer"
    
    for m in exec_methods:
        log_print(f"\nTesting {m}('{command_str}')...")
        try:
            method = getattr(app, m)
            res = method(command_str)
            log_print(f"  [SUCCESS] Result: {res}")
            
            # Check if B1 was created
            if aspen.Tree.FindNode(r"\Data\Blocks\B1"):
                log_print("  [VERIFIED] Block B1 created!")
        except Exception as e:
            log_print(f"  [FAIL] {str(e)[:100]}")

    # Test Script execution
    script_str = "Block MIXER MIXER B1"
    for m in exec_methods:
        log_print(f"\nTesting {m} with script format: '{script_str}'...")
        try:
            method = getattr(app, m)
            res = method(script_str)
            log_print(f"  [SUCCESS] Result: {res}")
        except Exception as e:
            log_print(f"  [FAIL] {str(e)[:100]}")

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
