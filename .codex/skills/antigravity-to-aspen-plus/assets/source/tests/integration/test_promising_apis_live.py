from __future__ import annotations

import os
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    os.environ.get("ASPEN_PLUS_INTEGRATION") != "1",
    reason="Set ASPEN_PLUS_INTEGRATION=1 to run live Aspen Plus registry/API probes",
)


def test_promising_aspen_progids_probe(tmp_path: Path) -> None:
    try:
        import win32com.client as win32
        import winreg
    except Exception as exc:  # pragma: no cover - environment-specific
        pytest.skip(f"Windows COM registry dependencies are not available: {exc}")

    log_path = tmp_path / "promising_apis_log.txt"
    lines: list[str] = []

    def log_print(message: str) -> None:
        print(message)
        lines.append(message)

    log_print("=" * 70)
    log_print("TESTING PROMISING ASPEN PLUS ProgIDs")
    log_print("=" * 70)
    log_print("\n[1] Scanning Registry for Aspen ProgIDs...")

    aspen_prog_ids: list[str] = []
    index = 0
    while True:
        try:
            key_name = winreg.EnumKey(winreg.HKEY_CLASSES_ROOT, index)
        except OSError:
            break
        index += 1
        if not any(keyword in key_name.lower() for keyword in ["aspen", "apwn", "aes"]):
            continue
        try:
            key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, key_name + "\\CLSID")
        except OSError:
            continue
        else:
            aspen_prog_ids.append(key_name)
            winreg.CloseKey(key)

    log_print(f"Found {len(aspen_prog_ids)} total Aspen ProgIDs")

    keywords = ["model", "block", "unit", "flowsheet", "simulation", "engine", "builder", "creator"]
    promising = [pid for pid in aspen_prog_ids if any(keyword in pid.lower() for keyword in keywords)]
    log_print(f"Found {len(promising)} promising ProgIDs:")
    for prog_id in promising[:30]:
        log_print(f"  - {prog_id}")

    log_print("\n[2] Testing Promising ProgIDs...")
    log_print("-" * 70)
    working_apis: list[tuple[str, list[str]]] = []

    for prog_id in promising[:50]:
        log_print(f"\nTrying: {prog_id}")
        try:
            obj = win32.Dispatch(prog_id)
            log_print(f"  [SUCCESS] Created: {obj}")
            methods = [method for method in dir(obj) if not method.startswith("_")]
            useful = [
                method
                for method in methods
                if any(keyword in method.lower() for keyword in ["add", "create", "new", "init", "block", "model"])
            ]
            if useful:
                log_print(f"  Useful methods: {useful[:10]}")
                working_apis.append((prog_id, useful))
            else:
                log_print(f"  Has {len(methods)} methods, none obviously useful")
        except Exception as exc:
            log_print(f"  [FAIL] {str(exc)[:60]}")

    log_print("\n[3] Testing All Apwn.* ProgIDs...")
    log_print("-" * 70)
    apwn_ids = [prog_id for prog_id in aspen_prog_ids if prog_id.startswith("Apwn.")]
    log_print(f"Found {len(apwn_ids)} Apwn.* ProgIDs:")
    for prog_id in apwn_ids:
        log_print(f"\n{prog_id}")
        try:
            obj = win32.Dispatch(prog_id)
            methods = [method for method in dir(obj) if not method.startswith("_")]
            log_print("  [OK] Works!")
            log_print(f"  Methods ({len(methods)}): {methods[:15]}")
        except Exception as exc:
            log_print(f"  [FAIL] {str(exc)[:40]}")

    log_print("\n" + "=" * 70)
    log_print("CONCLUSION")
    log_print("=" * 70)
    if working_apis:
        log_print(f"\nFound {len(working_apis)} potentially useful APIs")
    else:
        log_print("\nNo alternative APIs found with obvious block creation capabilities")

    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert log_path.is_file()
