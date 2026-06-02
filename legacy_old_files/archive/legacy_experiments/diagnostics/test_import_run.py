"""
Diagnostic: does Import() + Reinit() + Engine.Run2() work for INP files?

Run with:
    pixi run python diagnostics/test_import_run.py

Aspen Plus must be running (launched from Porticada).
"""

import sys
import time
from pathlib import Path

try:
    import win32com.client as win32
except ImportError:
    print("FAIL: win32com.client not available")
    sys.exit(1)

INP_PATH = str(
    Path(__file__).parent.parent
    / "process_runs"
    / "methanol"
    / "run_2026-05-07_13-50-56"
    / "methanol_generated.inp"
)


def node_count(aspen, path: str) -> int:
    try:
        node = aspen.Tree.FindNode(path)
        if node is None:
            return -1
        return int(node.Elements.Count)
    except Exception as e:
        print(f"  node_count({path}): error {e}")
        return -1


def main() -> None:
    print(f"INP path: {INP_PATH}")
    print()

    print("Step 1: DispatchEx → new Aspen instance")
    aspen = win32.DispatchEx("Apwn.Document")
    print("  OK")

    print("Step 2: InitNew()")
    aspen.InitNew()
    streams_before = node_count(aspen, r"\Data\Streams")
    blocks_before = node_count(aspen, r"\Data\Blocks")
    print(f"  \\Data\\Streams count after InitNew: {streams_before}")
    print(f"  \\Data\\Blocks  count after InitNew: {blocks_before}")
    print()

    print("Step 3: Import(inp_path)")
    try:
        aspen.Import(INP_PATH)
        print("  Import() returned without exception")
    except Exception as e:
        print(f"  Import() raised: {e}")
    streams_after_import = node_count(aspen, r"\Data\Streams")
    blocks_after_import = node_count(aspen, r"\Data\Blocks")
    print(f"  \\Data\\Streams count after Import: {streams_after_import}")
    print(f"  \\Data\\Blocks  count after Import: {blocks_after_import}")
    print()

    print("Step 4: Reinit()")
    try:
        aspen.Reinit()
        print("  Reinit() returned without exception")
    except Exception as e:
        print(f"  Reinit() raised: {e}")
    streams_after_reinit = node_count(aspen, r"\Data\Streams")
    blocks_after_reinit = node_count(aspen, r"\Data\Blocks")
    print(f"  \\Data\\Streams count after Reinit: {streams_after_reinit}")
    print(f"  \\Data\\Blocks  count after Reinit: {blocks_after_reinit}")
    print()

    print("Step 5: Engine.Run2(1) — async run, waiting up to 120s")
    start = time.time()
    try:
        aspen.Engine.Run2(1)
        while True:
            elapsed = time.time() - start
            if elapsed > 120:
                print("  Timed out waiting for run")
                aspen.Engine.Stop()
                break
            try:
                running = bool(aspen.Engine.IsRunning)
            except Exception:
                running = False
            if not running:
                print(f"  Run finished in {elapsed:.1f}s")
                break
            time.sleep(1)
    except Exception as e:
        print(f"  Engine.Run2 raised: {e}")
    streams_after_run = node_count(aspen, r"\Data\Streams")
    blocks_after_run = node_count(aspen, r"\Data\Blocks")
    print(f"  \\Data\\Streams count after Run: {streams_after_run}")
    print(f"  \\Data\\Blocks  count after Run: {blocks_after_run}")
    print()

    if streams_after_run > 0 and blocks_after_run > 0:
        print("RESULT: Import+Run works. Streams and blocks are populated after running.")
        print("        Fix: skip flowsheet pre-verification in com-auto build mode.")
    elif streams_after_import > 0 and blocks_after_import > 0:
        print("RESULT: Import alone works (no run needed).")
    else:
        print("RESULT: Import+Run did NOT populate the flowsheet tree.")
        print("        streams_after_run =", streams_after_run)
        print("        blocks_after_run  =", blocks_after_run)

    print()
    print("Step 6: Quit Aspen worker instance")
    try:
        aspen.Quit()
        print("  Quit OK")
    except Exception as e:
        print(f"  Quit raised: {e}")


if __name__ == "__main__":
    main()
