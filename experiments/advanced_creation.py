"""
RESEARCH: Advanced Block Creation
Testing different script commands and library specifications
"""
import win32com.client as win32
import time

log = open("advanced_creation_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS ADVANCED CREATION RESEARCH")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(5)
    aspen.Visible = True
    aspen.SuppressDialogs = 1
    
    # Test RunScript with various commands
    commands = [
        "BLOCK-NEW MIXER B1",
        "INSERT BLOCK B2 Mixer",
        "BLOCK B3 Mixer",
        "BLOCK B4 MIXER MIXER",
        "CREATE BLOCK B5 Mixer",
        "NEW BLOCK B6 Mixer"
    ]
    
    for cmd in commands:
        log_print(f"\nTesting RunScript('{cmd}')...")
        try:
            aspen.RunScript(cmd)
            log_print("  Call finished")
            time.sleep(1)
            # Check for block
            name = cmd.split()[2] if "NEW" in cmd or "INSERT" in cmd or "CREATE" in cmd else cmd.split()[1]
            if "BLOCK B3" in cmd: name = "B3"
            if "BLOCK B4" in cmd: name = "B4"
            if "B1" in cmd: name = "B1"
            
            node = aspen.Tree.FindNode(rf"\Data\Blocks\{name}")
            if node:
                log_print(f"  [VERIFIED] Block {name} created!")
            else:
                log_print(f"  [FAILED] {name} not found")
        except Exception as e:
            log_print(f"  [FAIL] {e}")

    # Test Elements.Add with library-prefixed types
    log_print("\nTesting Elements.Add with library prefixes...")
    blocks = aspen.Tree.FindNode(r"\Data\Blocks")
    prefixes = [
        "User Models.", "Built-In.", "Model Library.", 
        "Mixers.", "Splitters.", "Heaters.", "Flash.",
        "System.", "Global."
    ]
    
    for p in prefixes:
        t = p + "Mixer"
        log_print(f"  Trying Add('B10', '{t}')...")
        try:
            blocks.Elements.Add("B10", t)
            log_print(f"    [SUCCESS] Created with {t}")
            break
        except Exception as e:
            log_print(f"    [FAIL] {str(e)[:100]}")

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
