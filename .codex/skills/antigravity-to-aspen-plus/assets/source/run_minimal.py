from __future__ import annotations

import argparse
from pathlib import Path


LEGACY_PATH = Path("legacy_old_files/archive/root_probes/run_minimal_legacy.py")
NOTEBOOK_PATH = Path("notebooks/process_library_runner.ipynb")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compatibility wrapper for the archived minimal Aspen smoke script. "
            "Use the notebook-first batch workflow for supported Aspen runs."
        )
    )
    parser.add_argument(
        "--show-legacy-path",
        action="store_true",
        help="Print the archived legacy script path.",
    )
    args = parser.parse_args()

    if args.show_legacy_path:
        print(LEGACY_PATH)
        return 0

    print("This root entrypoint is kept for compatibility.")
    print(f"Legacy script: {LEGACY_PATH.as_posix()}")
    print(f"Supported workflow: open {NOTEBOOK_PATH.as_posix()} and run the batch-first cells.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
