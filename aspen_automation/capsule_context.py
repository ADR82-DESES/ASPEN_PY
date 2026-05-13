from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Any

from .batch_engine import discover_aspen_engine_path


APPANYWHERE_PROCESS_TOKENS = (
    "appanywhere",
    "appsanywhere",
    "cloudpaging",
    "software2",
    "s2apps",
    "s2launcher",
)
APPANYWHERE_ENV_TOKENS = (
    "APPANYWHERE",
    "APPSANYWHERE",
    "CLOUDPAGING",
    "SOFTWARE2",
    "S2APPS",
)
LOCALIZATION_ASSEMBLY_NAME = "AspenTech.AspenPlus.Localization"


def _run_command(command: list[str], *, timeout: int = 20) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:
        return {
            "status": "error",
            "command": command,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }

    return {
        "status": "completed",
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _powershell_executable() -> str | None:
    return shutil.which("powershell") or shutil.which("pwsh")


def _get_process_ancestry() -> dict[str, Any]:
    powershell = _powershell_executable()
    if powershell is None:
        return {
            "status": "skipped",
            "reason": "PowerShell was not found; process ancestry collection is Windows-specific.",
            "current_pid": os.getpid(),
            "parent_pid": os.getppid(),
        }

    command_text = (
        f"$TargetPid = {os.getpid()}; "
        "$items = @(); "
        "$guard = 0; "
        "while ($TargetPid -and $guard -lt 25) { "
        "  $p = Get-CimInstance Win32_Process -Filter \"ProcessId=$TargetPid\"; "
        "  if (-not $p) { break }; "
        "  $items += [pscustomobject]@{"
        "ProcessId=$p.ProcessId;"
        "ParentProcessId=$p.ParentProcessId;"
        "Name=$p.Name;"
        "ExecutablePath=$p.ExecutablePath;"
        "CommandLine=$p.CommandLine"
        "}; "
        "  $TargetPid = $p.ParentProcessId; "
        "  $guard += 1 "
        "}; "
        "$items | ConvertTo-Json -Depth 4"
    )
    result = _run_command(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command_text],
        timeout=20,
    )
    if result.get("status") != "completed" or result.get("returncode") != 0:
        return result | {"status": "error"}

    stdout = str(result.get("stdout", "")).strip()
    try:
        parsed = json.loads(stdout) if stdout else []
    except json.JSONDecodeError as exc:
        return result | {
            "status": "error",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }

    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        parsed = []

    return {
        "status": "collected",
        "current_pid": os.getpid(),
        "processes": parsed,
        "command": result.get("command"),
    }


def _read_text_property(obj: Any, property_name: str) -> str | None:
    try:
        value = getattr(obj, property_name)
    except Exception:
        return None
    if value is None or not isinstance(value, (str, int, float)):
        return None
    text = str(value).strip()
    return text or None


def _probe_com_identity(aspen: Any | None) -> dict[str, Any]:
    if aspen is None:
        return {"status": "skipped", "reason": "No Aspen COM object was available."}

    identity: dict[str, Any] = {"status": "collected", "document": {}, "application": {}}
    for property_name in ("Version", "Name", "FullName", "Path"):
        identity["document"][property_name] = _read_text_property(aspen, property_name)

    application = None
    try:
        application = getattr(aspen, "Application")
    except Exception as exc:
        identity["application_error"] = str(exc)

    if application is not None:
        for property_name in ("Version", "Name", "FullName", "Path"):
            identity["application"][property_name] = _read_text_property(application, property_name)

    return identity


def _detect_package_markers() -> dict[str, Any]:
    env_matches = {
        key: os.environ.get(key)
        for key in sorted(os.environ)
        if any(token in key.upper() for token in APPANYWHERE_ENV_TOKENS)
    }
    process_matches: list[str] = []
    tasklist = shutil.which("tasklist")
    tasklist_result: dict[str, Any] | None = None

    if tasklist is not None:
        tasklist_result = _run_command([tasklist, "/FO", "CSV", "/NH"], timeout=20)
        if tasklist_result.get("status") == "completed":
            for line in str(tasklist_result.get("stdout", "")).splitlines():
                lower_line = line.lower()
                if any(token in lower_line for token in APPANYWHERE_PROCESS_TOKENS):
                    process_matches.append(line)

    return {
        "status": "collected",
        "suspected_appanywhere_virtualization": bool(env_matches or process_matches),
        "matching_environment": env_matches,
        "matching_process_lines": process_matches[:50],
        "tasklist": tasklist_result
        if tasklist is not None
        else {"status": "skipped", "reason": "tasklist was not found."},
    }


def _probe_localization_assembly() -> dict[str, Any]:
    powershell = _powershell_executable()
    if powershell is None:
        return {
            "status": "skipped",
            "assembly": LOCALIZATION_ASSEMBLY_NAME,
            "reason": "PowerShell was not found; .NET assembly probing was skipped.",
        }

    command_text = (
        "try { "
        f"[System.Reflection.Assembly]::Load('{LOCALIZATION_ASSEMBLY_NAME}') | Out-Null; "
        "'visible' "
        "} catch { "
        "Write-Error $_.Exception.Message; exit 1 "
        "}"
    )
    result = _run_command(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command_text],
        timeout=20,
    )
    visible = result.get("status") == "completed" and result.get("returncode") == 0
    return result | {
        "status": "visible" if visible else "missing",
        "assembly": LOCALIZATION_ASSEMBLY_NAME,
        "visible": visible,
    }


def _probe_optional_diagnostic_tools() -> dict[str, Any]:
    procmon_path = shutil.which("procmon.exe") or shutil.which("Procmon64.exe")
    return {
        "fusion": {
            "status": "skipped",
            "reason": (
                "Fusion/.NET binding logging is optional and may require registry or admin changes; "
                "the capsule runner does not enable it automatically."
            ),
        },
        "procmon": {
            "status": "available" if procmon_path else "skipped",
            "path": procmon_path,
            "reason": (
                "ProcMon capture is optional and may require elevation; "
                "the capsule runner does not start it automatically."
            ),
        },
    }


def collect_capsule_context(
    *,
    aspen: Any | None = None,
    engine_path: str | Path | None = None,
) -> dict[str, Any]:
    resolved_engine_path = str(engine_path or discover_aspen_engine_path() or "")
    engine_file = Path(resolved_engine_path) if resolved_engine_path else None

    return {
        "timestamp_utc": _dt.datetime.now(_dt.UTC).isoformat(),
        "process": {
            "pid": os.getpid(),
            "parent_pid": os.getppid(),
            "python_executable": sys.executable,
            "cwd": os.getcwd(),
            "platform": platform.platform(),
        },
        "process_ancestry": _get_process_ancestry(),
        "resolved_aspen_engine": {
            "path": resolved_engine_path or None,
            "exists": bool(engine_file and engine_file.is_file()),
            "which_aspen": shutil.which("aspen"),
        },
        "com_identity": _probe_com_identity(aspen),
        "package_markers": _detect_package_markers(),
        "localization_assembly": _probe_localization_assembly(),
        "optional_diagnostics": _probe_optional_diagnostic_tools(),
    }


__all__ = [
    "APPANYWHERE_ENV_TOKENS",
    "APPANYWHERE_PROCESS_TOKENS",
    "LOCALIZATION_ASSEMBLY_NAME",
    "collect_capsule_context",
]
