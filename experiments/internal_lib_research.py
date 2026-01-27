"""
RESEARCH: Internal Library IDs
Testing internal sounding library names for block creation
"""
import win32com.client as win32
import time

log = open("internal_lib_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("ASPEN PLUS INTERNAL LIB RESEARCH")
log_print("="*70)

try:
    aspen = win32.Dispatch("Apwn.Document")
    aspen.InitNew()
    time.sleep(5)
    aspen.Visible = True
    aspen.SuppressDialogs = 1
    
    blocks = aspen.Tree.FindNode(r"\Data\Blocks")
    
    # Internal library names found in deep documentation/forums
    internal_libs = [
        "apwnbuilt-in",
        "ApwnBuilt-In",
        "Built-In",
        "Built-in",
        "Model Library",
        "ModelLibrary",
        "Mixers",
        "Mixer",
        "AP-Models",
        "User Models",
        "USER"
    ]
    
    for lib in internal_libs:
        log_print(f"Testing Add('B1', 'MIXER', '{lib}')...")
        try:
             # Wait, my previous test said it takes 1-2 arguments.
             # If it takes 2, then maybe the second argument is "MIXER|{lib}"?
             
             # Test 2-arg with separator
             try:
                 blocks.Elements.Add("B1", f"MIXER|{lib}")
                 log_print(f"  [SUCCESS] Created with 'MIXER|{lib}'")
                 break
             except:
                 pass
                 
             # Test 2-arg with comma
             try:
                 blocks.Elements.Add("B1", f"MIXER,{lib}")
                 log_print(f"  [SUCCESS] Created with 'MIXER,{lib}'")
                 break
             except:
                 pass

             # Test 2-arg with dot (already tried some but let's be thorough)
             try:
                 blocks.Elements.Add("B1", f"{lib}.MIXER")
                 log_print(f"  [SUCCESS] Created with '{lib}.MIXER'")
                 break
             except:
                 pass
                 
             # Test 3-arg just in case (maybe win32com error was wrong)
             try:
                 blocks.Elements.Add("B1", "MIXER", lib)
                 log_print(f"  [SUCCESS] Created with 3 args: ('B1', 'MIXER', '{lib}')")
                 break
             except Exception as e:
                 if "takes from 1 to 2 positional arguments" not in str(e):
                      log_print(f"  [INFO] 3-arg error was different: {str(e)[:50]}")

        except Exception as e:
            pass

except Exception as e:
    log_print(f"Error: {e}")

log_print("\n" + "="*70)
log_print("RESEARCH COMPLETE")
log_print("="*70)
log.close()
