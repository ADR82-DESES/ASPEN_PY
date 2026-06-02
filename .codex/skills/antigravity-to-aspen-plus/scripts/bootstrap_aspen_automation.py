from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CopySummary:
    copied: int = 0
    overwritten: int = 0
    unchanged: int = 0
    skipped: int = 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Copy the bundled batch-first Aspen Plus automation source code "
            "from this Codex skill into a target project."
        )
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path.cwd(),
        help="Target project directory. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite conflicting existing files. Directories are merged; files are never deleted.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be copied without writing files.",
    )
    return parser


def _same_file_contents(source: Path, destination: Path) -> bool:
    try:
        return filecmp.cmp(source, destination, shallow=False)
    except OSError:
        return False


def copy_source_tree(source_root: Path, target_root: Path, *, force: bool, dry_run: bool) -> CopySummary:
    summary = CopySummary()
    conflicts: list[Path] = []

    for source_path in sorted(path for path in source_root.rglob("*") if path.is_file()):
        relative_path = source_path.relative_to(source_root)
        destination_path = target_root / relative_path

        if destination_path.exists():
            if destination_path.is_file() and _same_file_contents(source_path, destination_path):
                summary.unchanged += 1
                continue
            if not force:
                summary.skipped += 1
                conflicts.append(relative_path)
                continue
            action = "overwrite"
            summary.overwritten += 1
        else:
            action = "copy"
            summary.copied += 1

        if dry_run:
            print(f"{action}: {relative_path}")
            continue

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)

    if conflicts:
        print("Skipped existing files with different contents:")
        for path in conflicts[:50]:
            print(f"  {path}")
        if len(conflicts) > 50:
            print(f"  ... {len(conflicts) - 50} more")
        print("Rerun with --force to overwrite conflicting files.")

    return summary


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    skill_root = Path(__file__).resolve().parents[1]
    source_root = skill_root / "assets" / "source"
    target_root = args.target.resolve()

    if not source_root.is_dir():
        parser.error(f"Bundled source tree was not found: {source_root}")

    print(f"Bundled source: {source_root}")
    print(f"Target project: {target_root}")
    if args.dry_run:
        print("Dry run: no files will be written.")

    summary = copy_source_tree(source_root, target_root, force=args.force, dry_run=args.dry_run)
    print(
        "Summary: "
        f"copied={summary.copied}, "
        f"overwritten={summary.overwritten}, "
        f"unchanged={summary.unchanged}, "
        f"skipped={summary.skipped}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
