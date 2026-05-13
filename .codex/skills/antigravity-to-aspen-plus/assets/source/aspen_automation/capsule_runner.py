from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .process_library import (
    ProcessRunResult,
    _resolve_batch_first_spec_path,
    run_process_batch_first,
)


def _resolve_job_path(value: str | Path, base_dir: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def resolve_capsule_job(job: Mapping[str, Any], *, base_dir: str | Path | None = None) -> dict[str, Any]:
    if not isinstance(job, Mapping):
        raise ValueError("Capsule job must be a JSON object.")

    root = Path(base_dir).expanduser().resolve() if base_dir is not None else Path.cwd()
    process_dir_value = job.get("process_dir")
    if not process_dir_value:
        raise ValueError("Capsule job requires process_dir; spec_path is only an optional debug override.")

    process_dir = _resolve_job_path(str(process_dir_value), root)
    spec_path = None
    if job.get("spec_path"):
        spec_path = _resolve_job_path(str(job["spec_path"]), root)
    canonical_spec = _resolve_batch_first_spec_path(process_dir, spec_path=spec_path)

    runs_root_value = job.get("runs_root", "process_runs")
    runs_root = _resolve_job_path(str(runs_root_value), root)

    engine_path = None
    if job.get("engine_path"):
        engine_path = _resolve_job_path(str(job["engine_path"]), root)

    return {
        "process_dir": process_dir,
        "spec_path": canonical_spec,
        "runs_root": runs_root,
        "visible": bool(job.get("visible", False)),
        "enforce_acceptance_targets": bool(job.get("enforce_acceptance_targets", False)),
        "timeout_seconds": int(job.get("timeout_seconds", 1800)),
        "batch_timeout_seconds": int(job.get("batch_timeout_seconds", 1800)),
        "report_format": str(job.get("report_format", "html")),
        "engine_path": str(engine_path) if engine_path is not None else None,
    }


def run_capsule_job(job_path: str | Path) -> ProcessRunResult:
    path = Path(job_path).expanduser().resolve()
    job = json.loads(path.read_text(encoding="utf-8"))
    resolved = resolve_capsule_job(job, base_dir=path.parent)
    return run_process_batch_first(
        resolved["process_dir"],
        resolved["runs_root"],
        visible=resolved["visible"],
        enforce_acceptance_targets=resolved["enforce_acceptance_targets"],
        spec_path=resolved["spec_path"],
        timeout_seconds=resolved["timeout_seconds"],
        batch_timeout_seconds=resolved["batch_timeout_seconds"],
        report_format=resolved["report_format"],
        engine_path=resolved["engine_path"],
    )


def main(argv: list[str] | None = None) -> int:
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("Usage: python -m aspen_automation.capsule_runner <job.json>")
        return 2

    result = run_capsule_job(args[0])
    print(json.dumps(result.to_summary_row(), indent=2, default=str))
    return 0 if result.succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["resolve_capsule_job", "run_capsule_job", "main"]
