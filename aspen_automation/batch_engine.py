from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_ASPEN_V14_ENGINE_PATH = (
    r"C:\Program Files\AspenTech\Aspen Plus V14.0\Engine\Xeq\aspen.exe"
)
ASPEN_ENGINE_ENV = "ASPEN_ENGINE_PATH"
ASPEN_BATCH_SUFFIXES = (
    ".bkp",
    ".cmd",
    ".def",
    ".his",
    ".log",
    ".out",
    ".rep",
    ".rp1",
    ".rp2",
    ".sta",
    ".sum",
)


@dataclass(frozen=True)
class AspenBatchResult:
    engine_path: str | None
    command: list[str]
    batch_dir: str
    input_path: str
    run_id: str
    returncode: int | None
    timed_out: bool
    elapsed_seconds: float
    stdout_path: str
    stderr_path: str
    artifacts: dict[str, dict[str, Any]]
    history_diagnostics: dict[str, Any]
    taskkill_diagnostics: dict[str, Any] | None = None
    error: str | None = None

    @property
    def archive_path(self) -> str | None:
        artifact = self.artifacts.get(".bkp")
        if not artifact or not artifact.get("exists"):
            return None
        return str(artifact["path"])

    @property
    def succeeded(self) -> bool:
        return not self.timed_out and self.archive_path is not None and self.error is None

    def to_diagnostics(self) -> dict[str, Any]:
        return {
            "engine_path": self.engine_path,
            "command": list(self.command),
            "batch_dir": self.batch_dir,
            "input_path": self.input_path,
            "run_id": self.run_id,
            "returncode": self.returncode,
            "timed_out": self.timed_out,
            "elapsed_seconds": self.elapsed_seconds,
            "stdout_path": self.stdout_path,
            "stderr_path": self.stderr_path,
            "artifacts": self.artifacts,
            "archive_path": self.archive_path,
            "succeeded": self.succeeded,
            "history_diagnostics": self.history_diagnostics,
            "taskkill_diagnostics": self.taskkill_diagnostics,
            "error": self.error,
        }


def discover_aspen_engine_path() -> str | None:
    env_path = os.environ.get(ASPEN_ENGINE_ENV)
    if env_path:
        return env_path

    path_candidate = shutil.which("aspen")
    if path_candidate:
        return path_candidate

    return DEFAULT_ASPEN_V14_ENGINE_PATH


def sanitize_run_id(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "", text.lower())
    if not normalized:
        normalized = "aspen"
    if len(normalized) <= 8:
        return normalized

    digest = hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:2]
    return f"{normalized[:6]}{digest}"


def make_unique_run_id(text: str, batch_dir: str | Path) -> str:
    batch_path = Path(batch_dir)
    base = sanitize_run_id(text)
    candidate = base
    for index in range(1, 100):
        if not any(batch_path.joinpath(f"{candidate}{suffix}").exists() for suffix in ASPEN_BATCH_SUFFIXES):
            return candidate
        suffix = f"{index:02d}"
        candidate = f"{base[: 8 - len(suffix)]}{suffix}"
    raise RuntimeError(f"Unable to allocate a unique Aspen run ID in {batch_path}")


def _file_diagnostics(path: str | Path) -> dict[str, Any]:
    resolved = Path(path)
    try:
        stat = resolved.stat()
    except OSError as exc:
        return {
            "path": str(resolved),
            "exists": False,
            "size_bytes": None,
            "error": str(exc),
        }

    return {
        "path": str(resolved),
        "exists": True,
        "size_bytes": stat.st_size,
        "modified_time": stat.st_mtime,
    }


def _read_text_lossy(path: str | Path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        try:
            return Path(path).read_text(encoding="latin-1", errors="replace")
        except OSError:
            return ""


def _load_source_lines(source_inp_path: str | Path | None) -> list[str]:
    if source_inp_path is None:
        return []
    try:
        return Path(source_inp_path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def parse_aspen_history(
    history_path: str | Path,
    *,
    source_inp_path: str | Path | None = None,
    max_messages: int = 40,
) -> dict[str, Any]:
    history_file = Path(history_path)
    file_info = _file_diagnostics(history_file)
    text = _read_text_lossy(history_file)
    source_lines = _load_source_lines(source_inp_path)
    lines = text.splitlines()

    summary_counts: dict[str, dict[str, int]] = {}
    summary_patterns = {
        "terminal_errors": r"TERMINAL\s+ERRORS\s+(\d+)\s+(\d+)\s+(\d+)",
        "severe_errors": r"SEVERE\s+ERRORS\s+(\d+)\s+(\d+)\s+(\d+)",
        "errors": r"(?<!TERMINAL\s)(?<!SEVERE\s)\bERRORS\s+(\d+)\s+(\d+)\s+(\d+)",
        "warnings": r"WARNINGS\s+(\d+)\s+(\d+)\s+(\d+)",
    }
    for key, pattern in summary_patterns.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            summary_counts[key] = {
                "physical_property": int(match.group(1)),
                "system": int(match.group(2)),
                "simulation": int(match.group(3)),
            }

    messages: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        upper_line = line.upper()
        if "SEVERE ERROR" in upper_line:
            severity = "severe"
        elif re.search(r"\*\*\s+ERROR\b", upper_line):
            severity = "error"
        elif " WARNING " in f" {upper_line} ":
            severity = "warning"
        else:
            continue

        block = [line.rstrip()]
        for follow in lines[index + 1 : index + 7]:
            if not follow.strip():
                break
            block.append(follow.rstrip())

        block_text = "\n".join(block)
        line_number = None
        line_match = re.search(r"LINE(?:\s+NUMBER)?\D+(\d+)", block_text, flags=re.IGNORECASE)
        if line_match:
            line_number = int(line_match.group(1))

        source_excerpt = None
        if line_number is not None and 1 <= line_number <= len(source_lines):
            source_excerpt = source_lines[line_number - 1].strip()

        messages.append(
            {
                "severity": severity,
                "history_line": index + 1,
                "input_line": line_number,
                "message": block_text.strip(),
                "source_excerpt": source_excerpt,
            }
        )
        if len(messages) >= max_messages:
            break

    total_errors = 0
    for key in ("terminal_errors", "severe_errors", "errors"):
        total_errors += sum(summary_counts.get(key, {}).values())

    input_translation_failed = bool(
        re.search(r"SIMULATION PROGRAM CANNOT BE EXECUTED", text, flags=re.IGNORECASE)
        or re.search(r"ERRORS IN INPUT TRANSLATION", text, flags=re.IGNORECASE)
    )

    if input_translation_failed or total_errors > 0:
        status = "failed"
    elif re.search(r"SIMULATION\s+COMPLETED|CALCULATIONS?\s+COMPLETED", text, flags=re.IGNORECASE):
        status = "converged"
    elif text.strip():
        status = "unknown"
    else:
        status = "missing"

    return {
        "history_file": file_info,
        "status": status,
        "input_translation_failed": input_translation_failed,
        "summary_counts": summary_counts,
        "messages": messages,
        "message_count": len(messages),
    }


def collect_batch_artifacts(batch_dir: str | Path, run_id: str) -> dict[str, dict[str, Any]]:
    batch_path = Path(batch_dir)
    return {
        suffix: _file_diagnostics(batch_path / f"{run_id}{suffix}")
        for suffix in ASPEN_BATCH_SUFFIXES
    }


def _terminate_process_tree(pid: int) -> dict[str, Any]:
    if os.name != "nt":
        return {"attempted": False, "reason": "process tree cleanup is Windows-specific"}

    completed = subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return {
        "attempted": True,
        "pid": pid,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def run_aspen_batch(
    inp_path: str | Path,
    work_dir: str | Path,
    *,
    run_id: str | None = None,
    timeout_seconds: int = 1800,
    make_backup: bool = True,
    engine_path: str | None = None,
) -> AspenBatchResult:
    source_path = Path(inp_path).resolve()
    batch_dir = Path(work_dir).resolve()
    batch_dir.mkdir(parents=True, exist_ok=True)

    resolved_run_id = make_unique_run_id(run_id or source_path.stem, batch_dir)
    batch_input = batch_dir / f"{resolved_run_id}.inp"
    if source_path != batch_input:
        shutil.copy2(source_path, batch_input)

    resolved_engine_path = engine_path or discover_aspen_engine_path()
    stdout_path = batch_dir / f"{resolved_run_id}.stdout.txt"
    stderr_path = batch_dir / f"{resolved_run_id}.stderr.txt"
    command: list[str] = []
    start = time.time()
    returncode: int | None = None
    timed_out = False
    error: str | None = None
    taskkill_diagnostics: dict[str, Any] | None = None

    if resolved_engine_path is None:
        error = (
            "Aspen Plus engine executable was not found. Set ASPEN_ENGINE_PATH "
            "or install Aspen Plus V14."
        )
    elif engine_path is not None and not Path(resolved_engine_path).is_file() and shutil.which(resolved_engine_path) is None:
        error = f"Aspen Plus engine executable was not found: {resolved_engine_path}"
    else:
        command = [resolved_engine_path, resolved_run_id, resolved_run_id]
        if make_backup:
            command.append("/mmbackup")
        command.append("/log")

        with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout_file, stderr_path.open(
            "w", encoding="utf-8", errors="replace"
        ) as stderr_file:
            try:
                process = subprocess.Popen(
                    command,
                    cwd=str(batch_dir),
                    stdout=stdout_file,
                    stderr=stderr_file,
                    text=True,
                )
            except OSError as exc:
                error = f"Aspen Plus engine executable could not be launched: {exc}"
            else:
                try:
                    returncode = process.wait(timeout=timeout_seconds)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    taskkill_diagnostics = _terminate_process_tree(process.pid)
                    try:
                        returncode = process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        returncode = None
                    error = f"Aspen batch engine timed out after {timeout_seconds} seconds."

    elapsed = time.time() - start
    artifacts = collect_batch_artifacts(batch_dir, resolved_run_id)
    history_path = artifacts[".his"]["path"]
    history_diagnostics = parse_aspen_history(history_path, source_inp_path=batch_input)
    if returncode not in (0, None) and error is None:
        error = f"Aspen batch engine exited with return code {returncode}."

    return AspenBatchResult(
        engine_path=resolved_engine_path,
        command=command,
        batch_dir=str(batch_dir),
        input_path=str(batch_input),
        run_id=resolved_run_id,
        returncode=returncode,
        timed_out=timed_out,
        elapsed_seconds=elapsed,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        artifacts=artifacts,
        history_diagnostics=history_diagnostics,
        taskkill_diagnostics=taskkill_diagnostics,
        error=error,
    )


__all__ = [
    "ASPEN_BATCH_SUFFIXES",
    "ASPEN_ENGINE_ENV",
    "AspenBatchResult",
    "collect_batch_artifacts",
    "discover_aspen_engine_path",
    "make_unique_run_id",
    "parse_aspen_history",
    "run_aspen_batch",
    "sanitize_run_id",
]
