import win32com.client as win32
import sys

print("=" * 60)
print("ASPEN PLUS CONNECTION TEST")
print("=" * 60)

# Test 1: GetActiveObject
print("\n[TEST 1] GetActiveObject('Apwn.Document')...")
try:
    aspen = win32.GetActiveObject("Apwn.Document")
    print("  ✓ SUCCESS - Connected to active instance")
    try:
        name = aspen.Name
        print(f"  ✓ Document Name: {name}")
        print(f"  ✓ Visible: {aspen.Visible}")
        sys.exit(0)  # Success!
    except Exception as e:
        print(f"  ✗ Could not read properties: {e}")
except Exception as e:
    print(f"  ✗ FAILED: {e}")

# Test 2: Dispatch
print("\n[TEST 2] Dispatch('Apwn.Document')...")
try:
    aspen = win32.Dispatch("Apwn.Document")
    print("  ✓ SUCCESS - Dispatch created/connected")
    try:
        name = aspen.Name
        print(f"  ✓ Document Name: {name}")
        print(f"  ✓ Visible: {aspen.Visible}")
        sys.exit(0)  # Success!
    except Exception as e:
        print(f"  ✗ Could not read properties: {e}")
except Exception as e:
    print(f"  ✗ FAILED: {e}")

# Test 3: DispatchEx
print("\n[TEST 3] DispatchEx('Apwn.Document')...")
try:
    aspen = win32.DispatchEx("Apwn.Document")
    print("  ✓ SUCCESS - DispatchEx created/connected")
    try:
        name = aspen.Name
        print(f"  ✓ Document Name: {name}")
        print(f"  ✓ Visible: {aspen.Visible}")
        sys.exit(0)  # Success!
    except Exception as e:
        print(f"  ✗ Could not read properties: {e}")
except Exception as e:
    print(f"  ✗ FAILED: {e}")

print("\n" + "=" * 60)
print("ALL CONNECTION METHODS FAILED")
print("=" * 60)
print("\nTroubleshooting:")
print("1. Is Aspen Plus installed?")
print("2. Is Aspen Plus currently running?")
print("3. Do you have a simulation file open in Aspen Plus?")
print("4. Try: File -> New -> Create blank simulation")
print("5. Keep Aspen Plus window open and run this script again")
sys.exit(1)
