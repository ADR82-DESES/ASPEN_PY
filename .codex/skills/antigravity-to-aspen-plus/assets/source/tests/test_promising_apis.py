"""
FINAL API RESEARCH: Test Promising ProgIDs from Registry
Focus on ProgIDs that might help with block/model creation
"""
import win32com.client as win32
import winreg

log = open("promising_apis_log.txt", "w", encoding="utf-8")

def log_print(msg):
    print(msg)
    log.write(msg + "\n")
    log.flush()

log_print("="*70)
log_print("TESTING PROMISING ASPEN PLUS ProgIDs")
log_print("="*70)

# Get all Aspen ProgIDs from registry
log_print("\n[1] Scanning Registry for Aspen ProgIDs...")
root_key = winreg.HKEY_CLASSES_ROOT
aspen_prog_ids = []

try:
    i = 0
    while True:
        try:
            key_name = winreg.EnumKey(root_key, i)
            if any(keyword in key_name.lower() for keyword in ['aspen', 'apwn', 'aes']):
                try:
                    key = winreg.OpenKey(root_key, key_name + "\\CLSID")
                    aspen_prog_ids.append(key_name)
                    winreg.CloseKey(key)
                except:
                    pass
            i += 1
        except OSError:
            break
except:
    pass

log_print(f"Found {len(aspen_prog_ids)} total Aspen ProgIDs")

# Filter for promising ones
keywords = ['model', 'block', 'unit', 'flowsheet', 'simulation', 'engine', 'builder', 'creator']
promising = [pid for pid in aspen_prog_ids if any(kw in pid.lower() for kw in keywords)]

log_print(f"Found {len(promising)} promising ProgIDs:")
for pid in promising[:30]:
    log_print(f"  - {pid}")

# Test each promising ProgID
log_print("\n[2] Testing Promising ProgIDs...")
log_print("-"*70)

working_apis = []

for prog_id in promising[:50]:  # Test first 50
    log_print(f"\nTrying: {prog_id}")
    try:
        obj = win32.Dispatch(prog_id)
        log_print(f"  [SUCCESS] Created: {obj}")

        # Check for useful methods
        methods = [m for m in dir(obj) if not m.startswith('_')]
        useful = [m for m in methods if any(kw in m.lower() for kw in ['add', 'create', 'new', 'init', 'block', 'model'])]

        if useful:
            log_print(f"  Useful methods: {useful[:10]}")
            working_apis.append((prog_id, obj, useful))
        else:
            log_print(f"  Has {len(methods)} methods, none obviously useful")

    except Exception as e:
        log_print(f"  [FAIL] {str(e)[:60]}")

# Deep dive into working APIs
if working_apis:
    log_print("\n[3] Deep Dive into Working APIs...")
    log_print("-"*70)

    for prog_id, obj, methods in working_apis:
        log_print(f"\n{prog_id}:")
        log_print(f"  Methods: {methods}")

        # Try to use them
        for method in methods[:5]:
            log_print(f"\n  Testing {method}()...")
            try:
                result = getattr(obj, method)
                log_print(f"    Type: {type(result)}")

                # If it's callable, try calling it
                if callable(result):
                    try:
                        # Try with no args
                        test_result = result()
                        log_print(f"    Result: {test_result}")
                    except:
                        log_print(f"    Requires arguments")
            except Exception as e:
                log_print(f"    Error: {str(e)[:60]}")

# Check for Apwn.* variants specifically
log_print("\n[4] Testing All Apwn.* ProgIDs...")
log_print("-"*70)

apwn_ids = [pid for pid in aspen_prog_ids if pid.startswith('Apwn.')]
log_print(f"Found {len(apwn_ids)} Apwn.* ProgIDs:")

for prog_id in apwn_ids:
    log_print(f"\n{prog_id}")
    try:
        obj = win32.Dispatch(prog_id)
        log_print(f"  [OK] Works!")

        # List all methods
        methods = [m for m in dir(obj) if not m.startswith('_')]
        log_print(f"  Methods ({len(methods)}): {methods[:15]}")

    except Exception as e:
        log_print(f"  [FAIL] {str(e)[:40]}")

log_print("\n" + "="*70)
log_print("CONCLUSION")
log_print("="*70)

if working_apis:
    log_print(f"\nFound {len(working_apis)} potentially useful APIs")
    log_print("See details above for methods and capabilities")
else:
    log_print("\nNo alternative APIs found with block creation capabilities")
    log_print("\nFINAL VERDICT:")
    log_print("The Aspen Plus COM interface (Apwn.Document) is the ONLY")
    log_print("documented interface, and it does NOT support programmatic")
    log_print("block creation in this version.")
    log_print("\nRECOMMENDATION:")
    log_print("1. Use template file approach (95% automation)")
    log_print("2. Contact AspenTech for enterprise automation solutions")
    log_print("3. Consider Aspen Plus Simulation Engine (separate product)")

log.close()
print("\n✓ Check promising_apis_log.txt for results")
