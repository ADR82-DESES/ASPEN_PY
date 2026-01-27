"""
ASPEN PLUS DIAGNOSTIC SUITE - Master Runner
Runs all diagnostic tests and generates a comprehensive report
"""
import subprocess
import sys
import time

print("="*80)
print("ASPEN PLUS DIAGNOSTIC SUITE - MASTER RUNNER")
print("="*80)
print("\nThis will run a comprehensive diagnostic suite to determine:")
print("  1. Connection capabilities")
print("  2. Tree structure and access")
print("  3. Programmatic flowsheet creation possibilities")
print("\nPlease ensure Aspen Plus is running before proceeding.")
print("="*80)

input("\nPress Enter to start diagnostics...")

# Run Part 1
print("\n" + "="*80)
print("RUNNING PART 1: System Information")
print("="*80)
try:
    result = subprocess.run(
        [sys.executable, "diagnostic_part1.py"],
        capture_output=True,
        text=True,
        timeout=30
    )
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    if result.returncode == 0:
        print("\n✓ Part 1 completed successfully")
    else:
        print(f"\n✗ Part 1 failed with exit code {result.returncode}")
except Exception as e:
    print(f"\n✗ Part 1 error: {e}")

time.sleep(2)

# Run Part 2
print("\n" + "="*80)
print("RUNNING PART 2: Tree Exploration")
print("="*80)
try:
    result = subprocess.run(
        [sys.executable, "diagnostic_part2.py"],
        capture_output=True,
        text=True,
        timeout=30
    )
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    if result.returncode == 0:
        print("\n✓ Part 2 completed successfully")
    else:
        print(f"\n✗ Part 2 failed with exit code {result.returncode}")
except Exception as e:
    print(f"\n✗ Part 2 error: {e}")

time.sleep(2)

# Run Part 3
print("\n" + "="*80)
print("RUNNING PART 3: Flowsheet Creation Test")
print("="*80)
print("\nWARNING: This will attempt to create elements in your Aspen Plus document.")
print("Make sure you have a backup or are using a blank document.")
proceed = input("Proceed with Part 3? (y/n): ")

if proceed.lower() == 'y':
    try:
        result = subprocess.run(
            [sys.executable, "diagnostic_part3.py"],
            capture_output=True,
            text=True,
            timeout=60
        )
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print("\n✓ Part 3 completed successfully")
        else:
            print(f"\n✗ Part 3 failed with exit code {result.returncode}")
    except Exception as e:
        print(f"\n✗ Part 3 error: {e}")
else:
    print("\n⊘ Part 3 skipped by user")

# Generate Final Report
print("\n" + "="*80)
print("GENERATING FINAL REPORT")
print("="*80)

report = """
ASPEN PLUS AUTOMATION DIAGNOSTIC REPORT
========================================

Date: {date}
Time: {time}

EXECUTIVE SUMMARY
-----------------
The diagnostic suite has completed testing your Aspen Plus installation
to determine the capabilities and limitations of COM automation.

KEY FINDINGS
------------
See the output above for detailed results from each test.

RECOMMENDATIONS
---------------
Based on the diagnostic results:

1. If Part 3 shows high success rate (>80%):
   → Full automation is possible
   → Use the automated scripts to create flowsheets programmatically

2. If Part 3 shows medium success rate (50-80%):
   → Partial automation is possible
   → Some manual setup required, then automation can handle the rest

3. If Part 3 shows low success rate (<50%):
   → Manual setup recommended
   → Use automation only for setting inputs, running, and extracting results

NEXT STEPS
----------
1. Review the diagnostic output above
2. Check your Aspen Plus window to see what was created
3. Based on the success rate, choose the appropriate automation approach
4. Refer to AUTOMATION_GUIDE.md for detailed instructions

FILES GENERATED
---------------
- diagnostic_results.json (if Part 2 completed)
- This console output

For support, provide this diagnostic output along with:
- Your Aspen Plus version
- Windows version
- Python version: {python_version}
"""

from datetime import datetime
report = report.format(
    date=datetime.now().strftime("%Y-%m-%d"),
    time=datetime.now().strftime("%H:%M:%S"),
    python_version=sys.version
)

print(report)

# Save report
try:
    with open("diagnostic_report.txt", 'w') as f:
        f.write(report)
    print("\n✓ Report saved to diagnostic_report.txt")
except:
    print("\n⚠ Could not save report to file")

print("\n" + "="*80)
print("DIAGNOSTICS COMPLETE")
print("="*80)
