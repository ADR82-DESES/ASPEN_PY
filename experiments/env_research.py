"""
RESEARCH: Block Creation with Proper Environment
Adding components and property methods BEFORE adding the block
"""
import win32com.client as win32
import time

log = open("env_research_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS ENVIRONMENT RESEARCH")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(5)
    aspen.Visible = True
    aspen.SuppressDialogs = 1
    
    # 1. Setup Components
    log_print("\n[1] Adding WATER component...")
    try:
        aspen.Tree.FindNode(r"\Data\Components\Specifications\Input\CAG_IDS").Elements.Add("WATER")
        log_print("  [OK] WATER added")
    except Exception as e:
        log_print(f"  [FAIL] {e}")

    # 2. Setup Property Method
    log_print("\n[2] Setting Property Method to IDEAL...")
    try:
        aspen.Tree.FindNode(r"\Data\Properties\Global\Input\METHOD").Value = "IDEAL"
        log_print("  [OK] Method set")
    except Exception as e:
        log_print(f"  [FAIL] {e}")

    time.sleep(2)

    # 3. Try to add Mixer Block
    log_print("\n[3] Testing Block Creation...")
    blocks = aspen.Tree.FindNode(r"\Data\Blocks")
    
    test_types = ["MIXER", "Mixer", "MIX", "HEATER", "FLASH2"]
    
    for t in test_types:
        log_print(f"  Trying Elements.Add('B1', '{t}')...")
        try:
            blocks.Elements.Add("B1", t)
            log_print(f"    [SUCCESS] Block B1 created with type {t}!")
            break
        except Exception as e:
            log_print(f"    [FAIL] {str(e)[:100]}")

    # 4. Try adding via 'Input' node
    log_print("\n[4] Testing alternative tree paths...")
    paths = [
        r"\Data\Flowsheet\Blocks",
        r"\Data\Flowsheet\Unit Operations"
    ]
    for p in paths:
        log_print(f"  Trying {p}...")
        try:
            node = aspen.Tree.FindNode(p)
            if node:
                 node.Elements.Add("B2", "MIXER")
                 log_print(f"    [SUCCESS] Created at {p}")
        except Exception as e:
            log_print(f"    [FAIL] {str(e)[:50]}")

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
