import os
import re
import time
import logging
import datetime
import shutil
import multiprocessing
import queue as queue_module
import csv
import io
import json
import subprocess
from typing import Optional, Dict, Any, Union, List
from dataclasses import dataclass, field

from .schema import PlantSpecification
from .com_builder import build_flowsheet_via_com
from .inp_generator import generate_inp
from .exceptions import AspenConnectionError, AspenNotRunningError, BuildError, SimulationError, ValidationError
from .parser import load_spec
from .simulation_diagnostics import read_aspen_run_diagnostics
from .validator import validate_spec

# Comment 4: Cleanup and logging behaviors
logger = logging.getLogger("aspen_automation.session")

ASPEN_DOCUMENT_PROG_ID = "Apwn.Document"
ASPEN_V14_OLE_MAJOR_VERSION = "40"
ASPEN_V14_SEED_FILE_ENV = "ASPEN_PLUS_V14_SEED_FILE"
DEFAULT_BUILD_TIMEOUT_SECONDS = 180
ASPEN_V14_SEED_FILE_CANDIDATES = (
    r"C:\Program Files\AspenTech\Aspen Plus V14.0\Favorites\testprob.bkp",
    r"C:\Program Files\AspenTech\Aspen Plus V14.0\GUI\Xeq\Blank.apt",
)
_LAST_DISPATCH_MODE = "unknown"
_LAST_DISPATCH_FALLBACK_ERROR: Optional[str] = None

def log(msg: str, level: str = "INFO") -> None:
    normalized_level = level.upper()
    log_level = getattr(logging, normalized_level, logging.INFO)
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {normalized_level}: {msg}")
    logger.log(log_level, msg)

# Import Guard
try:
    import win32com.client as win32
except ImportError:
    win32 = None

try:
    import pythoncom
except ImportError:
    pythoncom = None

# Comment 1: SessionResult shape and build_mode values
@dataclass
class SessionResult:
    """Result of a simulation session."""
    convergence_status: str = "unknown" # converged/failed/timeout/unknown
    build_mode: str = "auto" # inp-only, com-only, auto
    build_mechanism_used: str = "none"
    build_fallback_attempted: bool = False
    simulation_time_seconds: float = 0.0
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    status_messages: List[str] = field(default_factory=list)
    aspen: Any = None 

def _initialize_aspen_props(aspen: Any, visible: bool = True, suppress_dialogs: bool = True) -> None:
    """
    Safely sets Aspen properties after the application has been initialized.
    """
    if visible:
        aspen.Visible = 1
    else:
        aspen.Visible = 0

    if suppress_dialogs:
        try:
            aspen.SuppressDialogs = 1
        except AttributeError:
            logger.warning(
                "SuppressDialogs attribute not available on the Aspen COM object; "
                "dialog suppression skipped."
            )

def _read_text_property(obj: Any, property_name: str) -> Optional[str]:
    try:
        value = getattr(obj, property_name)
    except Exception:
        return None

    if value is None:
        return None

    if not isinstance(value, (str, int, float)):
        return None

    text = str(value).strip()
    return text or None


def _read_aspen_version(aspen: Any) -> Optional[str]:
    return _read_text_property(aspen, "Version")


def _probe_aspen_identity(aspen: Any) -> Dict[str, Any]:
    probe: Dict[str, Any] = {
        "document": {},
        "application": {},
    }

    for property_name in ("Version", "Name", "FullName", "Path"):
        probe["document"][property_name] = _read_text_property(aspen, property_name)

    application = None
    try:
        application = getattr(aspen, "Application")
    except Exception as e:
        probe["application_error"] = str(e)

    if application is not None:
        for property_name in ("Version", "Name", "FullName", "Path"):
            probe["application"][property_name] = _read_text_property(application, property_name)

    return probe


def _select_reported_aspen_version(identity_probe: Dict[str, Any]) -> Optional[str]:
    for scope in ("document", "application"):
        values = identity_probe.get(scope, {})
        if not isinstance(values, dict):
            continue
        version = values.get("Version")
        if version:
            return str(version)
    return None


def _is_aspen_v14_version(version: Optional[str]) -> bool:
    if not version:
        return False

    match = re.search(r"\d+(?:\.\d+)?", str(version))
    if match is None:
        return False

    return match.group(0).split(".", 1)[0] == ASPEN_V14_OLE_MAJOR_VERSION


def _close_aspen_document(aspen: Any) -> None:
    try:
        aspen.Close(False)
    except Exception:
        pass

    try:
        aspen.Quit()
    except Exception:
        pass


def _verify_aspen_v14_connection(
    aspen: Any,
    *,
    visible: bool = False,
    suppress_dialogs: bool = True,
) -> Dict[str, Any]:
    diagnostics: Dict[str, Any] = {
        "prog_id": ASPEN_DOCUMENT_PROG_ID,
        "expected_ole_major_version": ASPEN_V14_OLE_MAJOR_VERSION,
        "connection_verified": False,
        "v14_verified": False,
        "v14_version_verified": False,
        "version_status": "unknown",
        "preflight_status": "started",
    }

    identity_probe = _probe_aspen_identity(aspen)
    diagnostics["identity_probe"] = identity_probe
    version = _select_reported_aspen_version(identity_probe)
    diagnostics["aspen_version"] = version
    if version is None:
        diagnostics["version_status"] = "unreported"
    elif _is_aspen_v14_version(version):
        diagnostics["version_status"] = "v14"
        diagnostics["v14_version_verified"] = True
    else:
        diagnostics["version_status"] = "wrong_version"
        diagnostics["preflight_status"] = "wrong_version"
        raise AspenConnectionError(
            "Aspen Plus V14 connection check failed: "
            f"expected OLE version {ASPEN_V14_OLE_MAJOR_VERSION}.x, got {version!r}.",
            details=dict(diagnostics),
        )

    try:
        aspen.InitNew()
        diagnostics["init_new_success"] = True
    except Exception as e:
        diagnostics["init_new_success"] = False
        diagnostics["preflight_status"] = "init_failed"
        diagnostics["error"] = str(e)
        diagnostics["error_type"] = type(e).__name__
        raise AspenConnectionError(
            f"Aspen Plus V14 connection check failed during InitNew(): {e}",
            details=dict(diagnostics),
        )

    try:
        _initialize_aspen_props(aspen, visible=visible, suppress_dialogs=suppress_dialogs)
        diagnostics["properties_initialized"] = True
    except Exception as e:
        diagnostics["properties_initialized"] = False
        diagnostics["preflight_status"] = "property_initialization_failed"
        diagnostics["error"] = str(e)
        diagnostics["error_type"] = type(e).__name__
        raise AspenConnectionError(
            f"Aspen Plus V14 connection check failed while setting document properties: {e}",
            details=dict(diagnostics),
        )

    if version is None:
        identity_probe = _probe_aspen_identity(aspen)
        diagnostics["identity_probe"] = identity_probe
        version = _select_reported_aspen_version(identity_probe)
        diagnostics["aspen_version"] = version
        if version is None:
            diagnostics["version_status"] = "unreported"
        elif _is_aspen_v14_version(version):
            diagnostics["version_status"] = "v14"
            diagnostics["v14_version_verified"] = True
        else:
            diagnostics["version_status"] = "wrong_version"
            diagnostics["preflight_status"] = "wrong_version"
            raise AspenConnectionError(
                "Aspen Plus V14 connection check failed: "
                f"expected OLE version {ASPEN_V14_OLE_MAJOR_VERSION}.x, got {version!r}.",
                details=dict(diagnostics),
            )

    try:
        data_node = aspen.Tree.FindNode(r"\Data")
    except Exception as e:
        diagnostics["data_node_present"] = False
        diagnostics["preflight_status"] = "tree_unavailable"
        diagnostics["error"] = str(e)
        diagnostics["error_type"] = type(e).__name__
        raise AspenConnectionError(
            f"Aspen Plus V14 connection check failed: Aspen tree is unavailable after InitNew(): {e}",
            details=dict(diagnostics),
        )

    if data_node is None:
        diagnostics["data_node_present"] = False
        diagnostics["preflight_status"] = "data_node_missing"
        raise AspenConnectionError(
            "Aspen Plus V14 connection check failed: \\Data node is unavailable after InitNew().",
            details=dict(diagnostics),
        )

    diagnostics["data_node_present"] = True
    diagnostics["tree_initialized"] = True
    diagnostics["connection_verified"] = True
    diagnostics["v14_verified"] = bool(diagnostics["v14_version_verified"])
    diagnostics["preflight_status"] = (
        "v14_connected" if diagnostics["v14_version_verified"] else "connected_version_unreported"
    )
    return diagnostics


def check_aspen_v14_connection(
    *,
    visible: bool = False,
    suppress_dialogs: bool = True,
    keep_alive: bool = False,
) -> Dict[str, Any]:
    """
    Verify that Aspen Plus V14 can be reached through COM and initialized.

    Aspen Plus V14 exposes OLE Services as version 40.x. The check initializes a
    temporary blank document and verifies the root Aspen data tree before any
    build/import work is attempted.
    """
    aspen = None
    try:
        aspen = _connect_aspen()
        diagnostics = _verify_aspen_v14_connection(
            aspen,
            visible=visible,
            suppress_dialogs=suppress_dialogs,
        )
        diagnostics["dispatch_mode"] = _LAST_DISPATCH_MODE
        if _LAST_DISPATCH_FALLBACK_ERROR:
            diagnostics["dispatch_ex_error"] = _LAST_DISPATCH_FALLBACK_ERROR
        diagnostics["keep_alive"] = keep_alive
        return diagnostics
    finally:
        if aspen is not None and not keep_alive:
            _close_aspen_document(aspen)

def _connect_aspen() -> Any:
    """
    Connects to the Aspen Plus Engine. Returns the raw COM object.
    Does NOT set properties like Visible or SuppressDialogs yet,
    as some Aspen versions (e.g. 40.0) require initialization first.
    """
    global _LAST_DISPATCH_MODE, _LAST_DISPATCH_FALLBACK_ERROR
    _LAST_DISPATCH_MODE = "unknown"
    _LAST_DISPATCH_FALLBACK_ERROR = None

    if win32 is None:
        raise AspenConnectionError("win32com.client is not available (not on Windows or pywin32 missing).")

    dispatch_ex = getattr(win32, "DispatchEx", None)
    if callable(dispatch_ex):
        try:
            aspen = dispatch_ex(ASPEN_DOCUMENT_PROG_ID)
            _LAST_DISPATCH_MODE = "DispatchEx"
            return aspen
        except Exception as e:
            _LAST_DISPATCH_FALLBACK_ERROR = str(e)

    try:
        aspen = win32.Dispatch(ASPEN_DOCUMENT_PROG_ID)
        _LAST_DISPATCH_MODE = "Dispatch"
        return aspen
    except Exception as e:
        # Comment 5: AspenConnectionError with details
        details: Dict[str, Any] = {"dispatch_mode": _LAST_DISPATCH_MODE, "dispatch_error": str(e)}
        if _LAST_DISPATCH_FALLBACK_ERROR:
            details["dispatch_ex_error"] = _LAST_DISPATCH_FALLBACK_ERROR
        raise AspenConnectionError(f"Failed to connect to Aspen Plus: {e}", details=details)


def check_aspen_running() -> bool:
    """Returns True if Aspen Plus is currently running and reachable via COM."""
    if win32 is None:
        return False
    try:
        win32.GetActiveObject(ASPEN_DOCUMENT_PROG_ID)
        return True
    except Exception:
        return False


def _node_summary(aspen: Any, path: str, *, sample_limit: int = 5) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "path": path,
        "present": False,
        "count": 0,
        "sample_names": [],
    }
    try:
        node = aspen.Tree.FindNode(path)
    except Exception:
        return summary

    if node is None:
        return summary

    summary["present"] = True
    elements = getattr(node, "Elements", None)
    if elements is None:
        summary["count"] = 1
        return summary

    count_obj = getattr(elements, "Count", None)
    try:
        count = int(count_obj)
    except Exception:
        count = 1

    summary["count"] = max(count, 0)
    limit = min(summary["count"], sample_limit)
    for index in range(1, limit + 1):
        try:
            element = elements.Item(index)
            name = getattr(element, "Name", None)
        except Exception:
            continue
        if name:
            summary["sample_names"].append(str(name))
    return summary

def _file_diagnostics(path: str) -> Dict[str, Any]:
    diagnostics: Dict[str, Any] = {
        "path": path,
        "exists": False,
        "size_bytes": None,
    }

    try:
        exists = os.path.exists(path)
    except Exception as e:
        diagnostics["error"] = str(e)
        return diagnostics

    diagnostics["exists"] = bool(exists)
    if not exists:
        return diagnostics

    try:
        diagnostics["size_bytes"] = os.path.getsize(path)
    except Exception as e:
        diagnostics["size_error"] = str(e)

    return diagnostics


def _v14_seed_file_candidates() -> List[str]:
    candidates: List[str] = []
    configured = os.environ.get(ASPEN_V14_SEED_FILE_ENV)
    if configured:
        candidates.append(configured)

    candidates.extend(ASPEN_V14_SEED_FILE_CANDIDATES)
    normalized: List[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        normalized.append(os.path.abspath(os.path.expandvars(candidate)))

    def seed_priority(path: str) -> tuple[int, str]:
        name = os.path.basename(path).lower()
        if name == "blank.apt":
            return (0, name)
        if name.endswith(".apt"):
            return (1, name)
        return (2, name)

    return sorted(normalized, key=seed_priority)


def _existing_v14_seed_files() -> List[str]:
    existing: List[str] = []
    for candidate in _v14_seed_file_candidates():
        try:
            if os.path.exists(candidate):
                existing.append(candidate)
                continue
        except Exception:
            pass

        parent, name = os.path.split(candidate)
        if not parent or not name:
            continue
        try:
            for entry in os.scandir(parent):
                if entry.name.lower() != name.lower():
                    continue
                try:
                    entry.stat()
                except Exception:
                    pass
                existing.append(entry.path)
                break
        except Exception:
            continue
    return existing


def _seed_initialization_methods(seed_path: str) -> tuple[str, ...]:
    if os.path.splitext(seed_path)[1].lower() == ".apt":
        return ("InitFromFile2", "InitFromArchive2")
    return ("InitFromArchive2", "InitFromFile2")


def _write_worker_status(status_path: Optional[str], stage: str, **extra: Any) -> None:
    if not status_path:
        return

    payload: Dict[str, Any] = {
        "stage": stage,
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    payload.update(extra)
    try:
        os.makedirs(os.path.dirname(status_path), exist_ok=True)
        with open(status_path, "w", encoding="utf-8") as status_file:
            json.dump(payload, status_file, indent=2, default=str)
    except Exception:
        logger.debug("Unable to write Aspen worker status file", exc_info=True)


def _read_worker_status(status_path: Optional[str]) -> Dict[str, Any]:
    if not status_path:
        return {}
    try:
        with open(status_path, "r", encoding="utf-8") as status_file:
            payload = json.load(status_file)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _snapshot_aspen_processes() -> Dict[int, Dict[str, Any]]:
    try:
        completed = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq AspenPlus.exe", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception as e:
        logger.debug("Unable to snapshot AspenPlus processes: %s", e)
        return {}

    snapshot: Dict[int, Dict[str, Any]] = {}
    output = (completed.stdout or "").strip()
    if not output or output.upper().startswith("INFO:"):
        return snapshot

    for row in csv.reader(io.StringIO(output)):
        if len(row) < 2:
            continue
        try:
            pid = int(str(row[1]).strip())
        except ValueError:
            continue
        process_name = str(row[0]).strip()
        snapshot[pid] = {"pid": pid, "process_name": process_name}
    return snapshot


def _terminate_process_ids(process_ids: List[int]) -> List[Dict[str, Any]]:
    cleanup_results: List[Dict[str, Any]] = []
    for pid in sorted(set(process_ids)):
        record: Dict[str, Any] = {"pid": pid}
        try:
            completed = subprocess.run(
                ["taskkill", "/PID", str(pid), "/F", "/T"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            record["returncode"] = completed.returncode
            record["stdout"] = (completed.stdout or "").strip()
            record["stderr"] = (completed.stderr or "").strip()
            record["terminated"] = completed.returncode == 0
        except Exception as e:
            record["terminated"] = False
            record["error"] = str(e)
        cleanup_results.append(record)
    return cleanup_results


def _verify_flowsheet(aspen: Any) -> Dict[str, Any]:
    """Verify that Aspen populated a usable flowsheet tree after the build step."""
    streams = _node_summary(aspen, r"\Data\Streams")
    blocks = _node_summary(aspen, r"\Data\Blocks")
    build_valid = bool(streams["present"] and streams["count"] > 0 and blocks["present"] and blocks["count"] > 0)
    diagnostics = {
        "build_valid": build_valid,
        "flowsheet_verification": {
            "build_valid": build_valid,
            "stream_count": streams["count"],
            "block_count": blocks["count"],
            "stream_samples": streams["sample_names"],
            "block_samples": blocks["sample_names"],
            "streams_path": streams["path"],
            "blocks_path": blocks["path"],
        },
    }

    issues: List[str] = []
    if not streams["present"] or streams["count"] == 0:
        log("Verification: \\Data\\Streams node not found or empty.", level="WARNING")
        issues.append(
            f"Streams node missing or empty at {streams['path']} "
            f"(present={streams['present']}, count={streams['count']})."
        )
    if not blocks["present"] or blocks["count"] == 0:
        log("Verification: \\Data\\Blocks node not found or empty.", level="WARNING")
        issues.append(
            f"Blocks node missing or empty at {blocks['path']} "
            f"(present={blocks['present']}, count={blocks['count']})."
        )

    if issues:
        raise BuildError(
            "Aspen import did not materialize a usable flowsheet. " + " ".join(issues),
            mechanism_tried="verification",
            diagnostics=diagnostics,
        )

    log(
        "Verification: Aspen tree populated successfully "
        f"(streams={streams['count']}, blocks={blocks['count']})."
    )
    return diagnostics


def _generate_inp_file(
    spec: Union[PlantSpecification, Dict[str, Any]],
    path: str,
    *,
    build_mode: str,
    result: Optional[SessionResult] = None,
) -> str:
    try:
        generate_inp(spec, output_path=path)
    except ValidationError as e:
        diagnostics = {"inp_validation_report": e.report}
        if result is not None:
            result.diagnostics.update(diagnostics)
        raise BuildError(
            f"INP generation failed validation: {e}",
            build_mode=build_mode,
            mechanism_tried="generate_inp",
            diagnostics=diagnostics,
        ) from e
    except Exception as e:
        raise BuildError(
            f"INP generation failed: {e}",
            build_mode=build_mode,
            mechanism_tried="generate_inp",
        ) from e

    full_path = os.path.abspath(path)
    if result is not None:
        result.diagnostics["generated_inp_path"] = full_path
        result.diagnostics["generated_inp_file"] = _file_diagnostics(full_path)
    return full_path


def _com_path_variants(full_path: str) -> List[tuple[str, Any]]:
    variants: List[tuple[str, Any]] = []
    if win32 is not None and pythoncom is not None:
        try:
            variants.append(("bstr_variant", win32.VARIANT(pythoncom.VT_BSTR, full_path)))
        except Exception:
            pass
    variants.append(("raw_string", full_path))
    return variants


def _record_import_failure(
    attempts: List[Dict[str, Any]],
    mechanism: str,
    variant: str,
    error: Exception,
    *,
    source_path: Optional[str] = None,
) -> None:
    record: Dict[str, Any] = {
        "mechanism": mechanism,
        "path_variant": variant,
        "success": False,
        "error_type": type(error).__name__,
        "error": str(error),
    }
    if source_path is not None:
        record["source_path"] = source_path
    if isinstance(error, BuildError):
        record["diagnostics"] = dict(error.diagnostics)
    attempts.append(record)


def _coerce_running_state(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    return None


def _import_file_with_verification(
    aspen: Any,
    full_path: str,
    *,
    build_mode: str,
    settle_seconds: float = 2.0,
    prefer_seed: bool = False,
    initialize_blank: bool = False,
    visible: bool = False,
    suppress_dialogs: bool = True,
    status_path: Optional[str] = None,
    seed_files: Optional[List[str]] = None,
) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []
    last_error: Optional[Exception] = None
    last_verification: Dict[str, Any] = {}
    generated_file = _file_diagnostics(full_path)
    seed_candidates = _v14_seed_file_candidates()
    existing_seed_files = _existing_v14_seed_files() if seed_files is None else list(seed_files)

    def attempt_import(
        mechanism: str,
        variant: str,
        import_call,
        *,
        source_path: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        nonlocal last_error, last_verification
        try:
            _write_worker_status(
                status_path,
                "import_attempt_started",
                mechanism=mechanism,
                path_variant=variant,
                source_path=source_path,
                generated_inp_path=full_path,
            )
            import_call()
            _write_worker_status(
                status_path,
                "import_attempt_completed",
                mechanism=mechanism,
                path_variant=variant,
                source_path=source_path,
                generated_inp_path=full_path,
            )
            time.sleep(settle_seconds)
            verification = _verify_flowsheet(aspen)
            record = {
                "mechanism": mechanism,
                "path_variant": variant,
                "success": True,
                "flowsheet_verification": verification.get("flowsheet_verification", {}),
            }
            if source_path is not None:
                record["source_path"] = source_path
            attempts.append(record)
            diagnostics = {
                "generated_inp_path": full_path,
                "generated_inp_file": generated_file,
                "build_mechanism": mechanism,
                "import_path_variant": variant,
                "import_attempts": attempts,
                "v14_seed_file_candidates": seed_candidates,
                "v14_seed_files_found": existing_seed_files,
            }
            if source_path is not None:
                diagnostics["initialization_source_path"] = source_path
            diagnostics.update(verification)
            return diagnostics
        except Exception as e:
            last_error = e
            _write_worker_status(
                status_path,
                "import_attempt_failed",
                mechanism=mechanism,
                path_variant=variant,
                source_path=source_path,
                generated_inp_path=full_path,
                error_type=type(e).__name__,
                error=str(e),
            )
            if isinstance(e, BuildError):
                last_verification = dict(e.diagnostics)
            _record_import_failure(attempts, mechanism, variant, e, source_path=source_path)
            return None

    def attempt_all_import_mechanisms(
        *,
        mechanism_prefix: str = "",
        source_path: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        for variant, import_path in _com_path_variants(full_path):
            diagnostics = attempt_import(
                f"{mechanism_prefix}Import",
                variant,
                lambda p=import_path: aspen.Import(p),
                source_path=source_path,
            )
            if diagnostics is not None:
                return diagnostics

            def data_import(p=import_path) -> None:
                data_node = aspen.Tree.FindNode(r"\Data")
                if data_node is None:
                    raise AttributeError("\\Data node not available for Import")
                data_node.Import(p)

            diagnostics = attempt_import(
                f"{mechanism_prefix}Data.Import",
                variant,
                data_import,
                source_path=source_path,
            )
            if diagnostics is not None:
                return diagnostics

        diagnostics = attempt_import(
            f"{mechanism_prefix}ImportSimulation",
            "raw_string",
            lambda: aspen.ImportSimulation(full_path),
            source_path=source_path,
        )
        if diagnostics is not None:
            return diagnostics

        return None

    def attempt_seed_imports() -> Optional[Dict[str, Any]]:
        nonlocal last_error
        for seed_path in existing_seed_files:
            initialized = False
            initialization_method = ""
            for method_name in _seed_initialization_methods(seed_path):
                try:
                    _write_worker_status(
                        status_path,
                        "seed_initialization_started",
                        mechanism=method_name,
                        source_path=seed_path,
                    )
                    getattr(aspen, method_name)(seed_path)
                    _write_worker_status(
                        status_path,
                        "seed_initialization_completed",
                        mechanism=method_name,
                        source_path=seed_path,
                    )
                    _initialize_aspen_props(
                        aspen,
                        visible=visible,
                        suppress_dialogs=suppress_dialogs,
                    )
                    attempts.append(
                        {
                            "mechanism": method_name,
                            "path_variant": "v14_seed_file",
                            "source_path": seed_path,
                            "success": True,
                        }
                    )
                    initialized = True
                    initialization_method = method_name
                    break
                except Exception as e:
                    last_error = e
                    _write_worker_status(
                        status_path,
                        "seed_initialization_failed",
                        mechanism=method_name,
                        source_path=seed_path,
                        error_type=type(e).__name__,
                        error=str(e),
                    )
                    _record_import_failure(
                        attempts,
                        method_name,
                        "v14_seed_file",
                        e,
                        source_path=seed_path,
                    )

            if not initialized:
                continue

            diagnostics = attempt_all_import_mechanisms(
                mechanism_prefix=f"{initialization_method}+",
                source_path=seed_path,
            )
            if diagnostics is not None:
                return diagnostics

        return None

    def attempt_file_initializers() -> Optional[Dict[str, Any]]:
        for method_name in ("InitFromArchive2", "InitFromFile2"):
            for variant, import_path in _com_path_variants(full_path):
                diagnostics = attempt_import(
                    method_name,
                    variant,
                    lambda m=method_name, p=import_path: getattr(aspen, m)(p),
                )
                if diagnostics is not None:
                    return diagnostics
        return None

    def attempt_blank_imports() -> Optional[Dict[str, Any]]:
        nonlocal last_error
        if initialize_blank:
            try:
                _write_worker_status(status_path, "blank_initialization_started")
                aspen.InitNew()
                _write_worker_status(status_path, "blank_initialization_completed")
                _initialize_aspen_props(
                    aspen,
                    visible=visible,
                    suppress_dialogs=suppress_dialogs,
                )
                attempts.append(
                    {
                        "mechanism": "InitNew",
                        "path_variant": "blank_document",
                        "success": True,
                    }
                )
            except Exception as e:
                last_error = e
                _write_worker_status(
                    status_path,
                    "blank_initialization_failed",
                    error_type=type(e).__name__,
                    error=str(e),
                )
                _record_import_failure(attempts, "InitNew", "blank_document", e)

        diagnostics = attempt_all_import_mechanisms()
        if diagnostics is not None:
            return diagnostics
        return None

    if prefer_seed:
        diagnostics = attempt_seed_imports()
        if diagnostics is not None:
            return diagnostics
        diagnostics = attempt_blank_imports()
        if diagnostics is not None:
            return diagnostics
    else:
        diagnostics = attempt_blank_imports()
        if diagnostics is not None:
            return diagnostics
        diagnostics = attempt_file_initializers()
        if diagnostics is not None:
            return diagnostics
        diagnostics = attempt_seed_imports()
        if diagnostics is not None:
            return diagnostics

    failure_diagnostics = {
        "generated_inp_path": full_path,
        "generated_inp_file": generated_file,
        "build_mechanism": "Import",
        "import_attempts": attempts,
        "v14_seed_file_candidates": seed_candidates,
        "v14_seed_files_found": existing_seed_files,
    }
    if last_verification:
        for key in ("build_valid", "flowsheet_verification"):
            if key in last_verification:
                failure_diagnostics[key] = last_verification[key]

    raise BuildError(
        f"Aspen import did not materialize a usable flowsheet. Last error: {last_error}",
        build_mode=build_mode,
        mechanism_tried="Import",
        diagnostics=failure_diagnostics,
    )


def _aspen_inp_archive_worker(
    full_path: str,
    archive_path: str,
    status_path: str,
    visible: bool,
    suppress_dialogs: bool,
    result_queue: Any,
) -> None:
    """Import an INP in a disposable process and save a reloadable archive."""
    _write_worker_status(status_path, "worker_started", generated_inp_path=full_path)
    if pythoncom is not None:
        try:
            _write_worker_status(status_path, "coinitialize_started")
            pythoncom.CoInitialize()
            _write_worker_status(status_path, "coinitialize_completed")
        except Exception:
            _write_worker_status(status_path, "coinitialize_failed")
            pass

    aspen = None
    try:
        _write_worker_status(status_path, "connect_started")
        aspen = _connect_aspen()
        _write_worker_status(status_path, "connect_completed", dispatch_mode=_LAST_DISPATCH_MODE)
        identity_probe = _probe_aspen_identity(aspen)
        _write_worker_status(status_path, "inp_import_started")
        diagnostics = _import_file_with_verification(
            aspen,
            full_path,
            build_mode="auto",
            prefer_seed=False,
            initialize_blank=True,
            visible=visible,
            suppress_dialogs=suppress_dialogs,
            status_path=status_path,
        )
        diagnostics["identity_probe"] = identity_probe
        diagnostics["dispatch_mode"] = _LAST_DISPATCH_MODE
        if _LAST_DISPATCH_FALLBACK_ERROR:
            diagnostics["dispatch_ex_error"] = _LAST_DISPATCH_FALLBACK_ERROR

        _write_worker_status(status_path, "archive_save_started", compiled_archive_path=archive_path)
        aspen.SaveAs(archive_path)
        diagnostics["compiled_archive_path"] = archive_path
        diagnostics["compiled_archive_file"] = _file_diagnostics(archive_path)
        _write_worker_status(
            status_path,
            "archive_save_completed",
            compiled_archive_path=archive_path,
            compiled_archive_file=diagnostics["compiled_archive_file"],
        )
        diagnostics["build_worker_status_file"] = status_path
        diagnostics["build_worker_last_status"] = _read_worker_status(status_path)
        result_queue.put({"ok": True, "diagnostics": diagnostics})
    except BaseException as e:
        diagnostics = dict(getattr(e, "diagnostics", {}) or {})
        diagnostics.setdefault("generated_inp_path", full_path)
        diagnostics.setdefault("generated_inp_file", _file_diagnostics(full_path))
        diagnostics["compiled_archive_path"] = archive_path
        diagnostics["compiled_archive_file"] = _file_diagnostics(archive_path)
        diagnostics["build_worker_error_type"] = type(e).__name__
        diagnostics["build_worker_error"] = str(e)
        diagnostics["dispatch_mode"] = _LAST_DISPATCH_MODE
        if _LAST_DISPATCH_FALLBACK_ERROR:
            diagnostics["dispatch_ex_error"] = _LAST_DISPATCH_FALLBACK_ERROR
        _write_worker_status(
            status_path,
            "worker_failed",
            error_type=type(e).__name__,
            error=str(e),
            compiled_archive_path=archive_path,
        )
        diagnostics["build_worker_status_file"] = status_path
        diagnostics["build_worker_last_status"] = _read_worker_status(status_path)
        result_queue.put(
            {
                "ok": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "diagnostics": diagnostics,
            }
        )
    finally:
        if aspen is not None:
            _write_worker_status(status_path, "cleanup_started")
            _close_aspen_document(aspen)
            _write_worker_status(status_path, "cleanup_completed")
        if pythoncom is not None:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


def _build_inp_archive_with_worker(
    full_path: str,
    archive_path: str,
    *,
    timeout_seconds: int = DEFAULT_BUILD_TIMEOUT_SECONDS,
    visible: bool = False,
    suppress_dialogs: bool = True,
) -> Dict[str, Any]:
    full_path = os.path.abspath(full_path)
    archive_path = os.path.abspath(archive_path)
    status_path = os.path.join(os.path.dirname(archive_path), "inp_import_worker_status.json")
    aspen_processes_before = _snapshot_aspen_processes()
    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()
    process = ctx.Process(
        target=_aspen_inp_archive_worker,
        args=(full_path, archive_path, status_path, visible, suppress_dialogs, result_queue),
    )

    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(10)
        aspen_processes_after_timeout = _snapshot_aspen_processes()
        new_aspen_pids = sorted(set(aspen_processes_after_timeout) - set(aspen_processes_before))
        orphan_cleanup = _terminate_process_ids(new_aspen_pids)
        diagnostics = {
            "generated_inp_path": full_path,
            "generated_inp_file": _file_diagnostics(full_path),
            "compiled_archive_path": archive_path,
            "compiled_archive_file": _file_diagnostics(archive_path),
            "build_worker_status_file": status_path,
            "build_worker_last_status": _read_worker_status(status_path),
            "build_worker_timeout_seconds": timeout_seconds,
            "timed_out_attempt": "isolated_inp_import_worker",
            "build_worker_aspen_processes_before": aspen_processes_before,
            "build_worker_aspen_processes_after_timeout": aspen_processes_after_timeout,
            "build_worker_orphan_pids": new_aspen_pids,
            "build_worker_orphan_cleanup": orphan_cleanup,
            "import_attempts": [],
            "v14_seed_file_candidates": _v14_seed_file_candidates(),
            "v14_seed_files_found": _existing_v14_seed_files(),
        }
        raise BuildError(
            f"Aspen INP import worker timed out after {timeout_seconds} seconds.",
            build_mode="auto",
            mechanism_tried="isolated_inp_import_worker",
            diagnostics=diagnostics,
        )

    try:
        payload = result_queue.get(timeout=2)
    except queue_module.Empty:
        aspen_processes_after_exit = _snapshot_aspen_processes()
        new_aspen_pids = sorted(set(aspen_processes_after_exit) - set(aspen_processes_before))
        orphan_cleanup = _terminate_process_ids(new_aspen_pids)
        diagnostics = {
            "generated_inp_path": full_path,
            "generated_inp_file": _file_diagnostics(full_path),
            "compiled_archive_path": archive_path,
            "compiled_archive_file": _file_diagnostics(archive_path),
            "build_worker_status_file": status_path,
            "build_worker_last_status": _read_worker_status(status_path),
            "build_worker_timeout_seconds": timeout_seconds,
            "build_worker_exitcode": process.exitcode,
            "build_worker_aspen_processes_before": aspen_processes_before,
            "build_worker_aspen_processes_after_exit": aspen_processes_after_exit,
            "build_worker_orphan_pids": new_aspen_pids,
            "build_worker_orphan_cleanup": orphan_cleanup,
            "import_attempts": [],
            "v14_seed_file_candidates": _v14_seed_file_candidates(),
            "v14_seed_files_found": _existing_v14_seed_files(),
        }
        raise BuildError(
            f"Aspen INP import worker exited without diagnostics (exitcode={process.exitcode}).",
            build_mode="auto",
            mechanism_tried="isolated_inp_import_worker",
            diagnostics=diagnostics,
        )
    finally:
        result_queue.close()

    diagnostics = dict(payload.get("diagnostics", {}))
    diagnostics["build_worker_timeout_seconds"] = timeout_seconds
    diagnostics["build_worker_exitcode"] = process.exitcode
    diagnostics["build_worker_status_file"] = status_path
    diagnostics["build_worker_last_status"] = _read_worker_status(status_path)
    aspen_processes_after_exit = _snapshot_aspen_processes()
    new_aspen_pids = sorted(set(aspen_processes_after_exit) - set(aspen_processes_before))
    diagnostics["build_worker_aspen_processes_before"] = aspen_processes_before
    diagnostics["build_worker_aspen_processes_after_exit"] = aspen_processes_after_exit
    diagnostics["build_worker_orphan_pids"] = new_aspen_pids
    if new_aspen_pids:
        diagnostics["build_worker_orphan_cleanup"] = _terminate_process_ids(new_aspen_pids)
    if payload.get("ok"):
        return diagnostics

    raise BuildError(
        f"Aspen INP import worker failed: {payload.get('error')}",
        build_mode="auto",
        mechanism_tried="isolated_inp_import_worker",
        diagnostics=diagnostics,
    )


# Comment 2: Build workflows
def _build_inp_only(
    spec: Union[PlantSpecification, Dict[str, Any]], 
    path: str, 
    aspen: Any,
    result: Optional[SessionResult] = None,
    visible: bool = True,
    suppress_dialogs: bool = True
) -> None:
    """
    Generates INP, writes to temp file, calls InitFromFile2, and verifies flowsheet.
    """
    log(f"Build mode: inp-only. Target: {path}")
    
    full_path = _generate_inp_file(spec, path, build_mode="inp-only", result=result)
    
    # Call InitFromFile2
    try:
        aspen.InitFromFile2(full_path)
        _initialize_aspen_props(aspen, visible=visible, suppress_dialogs=suppress_dialogs)
        verification = _verify_flowsheet(aspen)
        if result is not None:
            result.diagnostics.update(verification)
    except BuildError as e:
        diagnostics = dict(e.diagnostics)
        diagnostics.setdefault("generated_inp_path", full_path)
        diagnostics.setdefault("generated_inp_file", _file_diagnostics(full_path))
        raise BuildError(
            str(e),
            build_mode="inp-only",
            mechanism_tried="verification",
            diagnostics=diagnostics,
        ) from e
    except Exception as e:
        diagnostics = dict(result.diagnostics) if result is not None else {}
        diagnostics.setdefault("generated_inp_path", full_path)
        diagnostics.setdefault("generated_inp_file", _file_diagnostics(full_path))
        diagnostics["InitFromFile2_error"] = str(e)
        raise BuildError(
            f"Failed to initialize from file: {e}",
            build_mode="inp-only",
            mechanism_tried="InitFromFile2",
            diagnostics=diagnostics,
        )

def _build_com_only(
    spec: Union[PlantSpecification, Dict[str, Any]], 
    aspen: Any, 
    result: SessionResult,
    visible: bool = True,
    suppress_dialogs: bool = True
) -> None:
    """
    Diagnostic COM-only path.
    """
    log("Build mode: com-only. Running InitNew...")
    
    # Run InitNew
    try:
        aspen.InitNew()
        _initialize_aspen_props(aspen, visible=visible, suppress_dialogs=suppress_dialogs)
    except Exception as e:
        raise BuildError(
            str(e),
            build_mode="com-only",
            mechanism_tried="InitNew",
        ) from e
    
    msg = "COM-only build depends on external config/library defaults"
    log(msg, level="WARNING")
    result.diagnostics["warning"] = msg
    result.build_mechanism_used = "COM"
    result.diagnostics["build_mechanism"] = "COM"

def _build_auto(
    spec: Union[PlantSpecification, Dict[str, Any]],
    path: str,
    aspen: Any,
    result: SessionResult,
    visible: bool = True,
    suppress_dialogs: bool = True,
    build_timeout_seconds: int = DEFAULT_BUILD_TIMEOUT_SECONDS,
) -> None:
    """
    Default build path based on the COM block-by-block builder scaffold.

    This avoids Aspen input-language import as the primary path and instead
    constructs the flowsheet directly through the live Aspen COM tree.
    """
    log(f"Build mode: auto. Target: {path}")
    result.build_mode = "auto"
    builder_diagnostics = build_flowsheet_via_com(spec, aspen)
    result.build_mechanism_used = builder_diagnostics.get("build_mechanism", "com_block_builder")
    result.diagnostics.update(builder_diagnostics)
    log("COM block-by-block build completed")


def _build_com_auto(
    spec: Union[PlantSpecification, Dict[str, Any]], 
    path: str, 
    aspen: Any, 
    result: SessionResult,
    visible: bool = True,
    suppress_dialogs: bool = True,
    build_timeout_seconds: int = DEFAULT_BUILD_TIMEOUT_SECONDS,
) -> None:
    """
    Legacy COM import path retained for diagnostics as build_mode="com-auto".
    """
    log(f"Build mode: com-auto. Target: {path}")
    result.build_mode = "com-auto"
    
    full_path = _generate_inp_file(spec, path, build_mode="com-auto", result=result)
    is_inp = path.lower().endswith(".inp")

    if is_inp:
        log("Detected .inp file - building reloadable archive in isolated Aspen worker...")
        archive_path = os.path.join(os.path.dirname(full_path), "compiled_from_inp.bkp")
        try:
            worker_diagnostics = _build_inp_archive_with_worker(
                full_path,
                archive_path,
                timeout_seconds=build_timeout_seconds,
                visible=visible,
                suppress_dialogs=suppress_dialogs,
            )
            result.diagnostics.update(worker_diagnostics)
            result.diagnostics["worker_import_diagnostics"] = dict(worker_diagnostics)
            compiled_archive_path = worker_diagnostics.get("compiled_archive_path", archive_path)
            try:
                aspen.InitFromArchive2(compiled_archive_path)
                _initialize_aspen_props(aspen, visible=visible, suppress_dialogs=suppress_dialogs)
                verification = _verify_flowsheet(aspen)
                log("Compiled archive load successful")
                result.build_mechanism_used = worker_diagnostics.get("build_mechanism", "isolated_inp_import_worker")
                result.diagnostics["build_mechanism"] = result.build_mechanism_used
                result.diagnostics["archive_load_mechanism"] = "InitFromArchive2"
                result.diagnostics.update(verification)
            except Exception as archive_error:
                result.build_fallback_attempted = True
                result.diagnostics["archive_load_mechanism"] = "InitFromArchive2"
                result.diagnostics["archive_load_error"] = str(archive_error)
                log(
                    "Compiled archive reload failed after a valid worker import; "
                    "trying active-session seed import.",
                    level="WARNING",
                )
                try:
                    active_import_diagnostics = _import_file_with_verification(
                        aspen,
                        full_path,
                        build_mode="com-auto",
                        prefer_seed=False,
                        initialize_blank=True,
                        visible=visible,
                        suppress_dialogs=suppress_dialogs,
                    )
                except BuildError as active_error:
                    result.diagnostics["active_session_import_error"] = str(active_error)
                    result.diagnostics["active_session_import_diagnostics"] = dict(active_error.diagnostics)
                    raise BuildError(
                        "Auto build failed for .inp file. Worker import succeeded, "
                        "archive reload failed, and active-session import fallback failed. "
                        f"Last error: {active_error}",
                        build_mode="com-auto",
                        mechanism_tried="active_session_seed_import",
                        diagnostics=result.diagnostics,
                    ) from active_error

                result.diagnostics["archive_load_fallback_used"] = True
                result.diagnostics["active_session_import_diagnostics"] = dict(active_import_diagnostics)
                result.diagnostics.update(active_import_diagnostics)
                result.build_mechanism_used = active_import_diagnostics.get(
                    "build_mechanism",
                    worker_diagnostics.get("build_mechanism", "active_session_seed_import"),
                )
                result.diagnostics["build_mechanism"] = result.build_mechanism_used
                log("Active-session seed import successful")
            return
        except BuildError as e:
            last_error = e
            result.build_fallback_attempted = True
            log(
                f"Isolated INP archive build failed: {e}",
                level="WARNING",
            )
            result.diagnostics["initial_import_error"] = str(e)
            result.diagnostics["initial_import_diagnostics"] = dict(e.diagnostics)
            result.diagnostics.update(e.diagnostics)
            try:
                active_import_diagnostics = _import_file_with_verification(
                    aspen,
                    full_path,
                    build_mode="com-auto",
                    prefer_seed=False,
                    initialize_blank=False,
                    visible=visible,
                    suppress_dialogs=suppress_dialogs,
                    seed_files=[],
                )
                result.diagnostics["worker_failure_active_import_fallback_used"] = True
                result.diagnostics["active_session_import_diagnostics"] = dict(active_import_diagnostics)
                result.diagnostics.update(active_import_diagnostics)
                result.build_mechanism_used = active_import_diagnostics.get("build_mechanism", "active_session_import")
                result.diagnostics["build_mechanism"] = result.build_mechanism_used
                log("Active-session import fallback successful")
                return
            except BuildError as active_error:
                result.diagnostics["active_session_import_error"] = str(active_error)
                result.diagnostics["active_session_import_diagnostics"] = dict(active_error.diagnostics)
            msg = f"COM auto build failed for .inp file. Isolated archive import failed. Last error: {last_error}"
            log(msg, level="ERROR")
            raise BuildError(
                msg,
                build_mode="com-auto",
                mechanism_tried="isolated_inp_import_worker",
                diagnostics=result.diagnostics,
            ) from e
        except Exception as e:
            last_error = e
            result.build_fallback_attempted = True
            log(f"Isolated INP archive build attempt failed: {e}", level="WARNING")
            result.diagnostics["initial_import_error"] = str(e)
            msg = f"COM auto build failed for .inp file. Isolated archive import failed. Last error: {last_error}"
            log(msg, level="ERROR")
            raise BuildError(
                msg,
                build_mode="com-auto",
                mechanism_tried="isolated_inp_import_worker",
                diagnostics=result.diagnostics,
            ) from e

    # Attempt 2: InitFromFile2 (Primary for .bkp/.apw, secondary for .inp)
    try:
        aspen.InitFromFile2(full_path)
        _initialize_aspen_props(aspen, visible=visible, suppress_dialogs=suppress_dialogs)
        verification = _verify_flowsheet(aspen)
        log("InitFromFile2 successful")
        result.build_mechanism_used = "InitFromFile2"
        result.diagnostics["build_mechanism"] = "InitFromFile2"
        result.diagnostics.update(verification)
        return
    except BuildError as e:
        diagnostics = dict(e.diagnostics)
        diagnostics["build_mechanism"] = "InitFromFile2"
        diagnostics.setdefault("generated_inp_path", full_path)
        raise BuildError(
            str(e),
            build_mode="com-auto",
            mechanism_tried="InitFromFile2",
            diagnostics=diagnostics,
        ) from e
    except Exception as e:
        # Fallback
        last_error = e
        log(f"InitFromFile2 failed: {e}. Attempting fallback...", level="WARNING")
        result.build_fallback_attempted = True
        result.diagnostics["InitFromFile2_error"] = str(e)

    # Final Fallback check if it wasn't already tried as primary
    if not is_inp:
        try:
            aspen.InitNew()
            _initialize_aspen_props(aspen, visible=visible, suppress_dialogs=suppress_dialogs)
            verification = _import_file_with_verification(aspen, full_path, build_mode="com-auto")
            log("Final Fallback Import successful")
            result.build_mechanism_used = verification.get("build_mechanism", "Import")
            result.diagnostics.update(verification)
            return
        except BuildError as e:
            diagnostics = dict(e.diagnostics)
            diagnostics["build_mechanism"] = "Import"
            diagnostics.setdefault("generated_inp_path", full_path)
            raise BuildError(
                str(e),
                build_mode="com-auto",
                mechanism_tried="Import",
                diagnostics=diagnostics,
            ) from e
        except Exception as e:
            last_error = e
            msg = f"COM auto build failed. InitFromFile2 and Import both failed. Last error: {last_error}"
            log(msg, level="ERROR")
            raise BuildError(msg, build_mode="com-auto", mechanism_tried="Import", diagnostics=result.diagnostics)
    else:
        msg = f"COM auto build failed for .inp file. Both primary Import and fallback InitFromFile2 failed. Last error: {last_error}"
        log(msg, level="ERROR")
        raise BuildError(msg, build_mode="com-auto", mechanism_tried="InitFromFile2", diagnostics=result.diagnostics)

# Comment 3: Simulation run flow
def _run_simulation(
    aspen: Any,
    timeout: int = 300,
    *,
    block_names: Optional[List[str]] = None,
) -> tuple[str, float, List[str], Dict[str, Any]]:
    """
    Runs the simulation.
    Returns: (status, elapsed_seconds)
    """
    log("Starting simulation run...")
    try:
        aspen.Reinit()
        aspen.Engine.Run2(1) # 1 = Async
        
        start_time = time.time()
        next_progress_log = 15.0
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                aspen.Engine.Stop()
                log(f"Simulation timed out after {elapsed:.2f}s", level="WARNING")
                return "timeout", elapsed, [], {"convergence_status": "timeout", "messages": []}
            
            # Check status using Document property
            is_running = False
            resolved_running = None
            try:
                resolved_running = _coerce_running_state(aspen.EngineRunning)
            except Exception:
                resolved_running = None

            if resolved_running is None:
                try:
                    resolved_running = _coerce_running_state(aspen.Engine.IsRunning)
                except Exception:
                    resolved_running = None

            if resolved_running is not None:
                is_running = resolved_running

            if resolved_running is False:
                break

            if elapsed >= next_progress_log:
                remaining = max(timeout - elapsed, 0.0)
                log(
                    (
                        "Simulation still running... "
                        f"elapsed={elapsed:.0f}s, remaining_budget={remaining:.0f}s"
                    )
                )
                next_progress_log += 15.0
                
            time.sleep(1)
            
        elapsed = time.time() - start_time
        
        diagnostics = read_aspen_run_diagnostics(aspen, block_names=block_names)
        status = str(diagnostics.get("convergence_status", "unknown")).strip().lower()
        if diagnostics.get("per_error_path"):
            log(
                f"Found convergence status at {diagnostics['per_error_path']}: "
                f"{diagnostics.get('per_error')} -> {status}"
            )
        elif diagnostics.get("status_source") not in {None, "unresolved"}:
            log(
                f"Convergence status (PER_ERROR) not found. "
                f"Inferred from {diagnostics['status_source']}: {status}",
                level="WARNING",
            )
        else:
            log("Convergence status could not be resolved from Aspen result nodes.", level="WARNING")

        messages = diagnostics.get("messages", [])
        log(f"Simulation finished with status: {status} in {elapsed:.2f}s")
        return status, elapsed, messages, diagnostics
        
    except Exception as e:
        raise SimulationError(f"Simulation execution failed: {e}", convergence_status="failed")

# Comment 4: Cleanup
def _cleanup_session(aspen: Any, output_dir: str, inp_path: Optional[str] = None, keep_alive: bool = False) -> None:
    if aspen:
        if not keep_alive:
            log("Cleaning up session... Closing and quitting Aspen.")
            try:
                aspen.Close(False)
            except Exception as e:
                logger.warning("Aspen Close(False) failed during cleanup: %s", e)
            try:
                aspen.Quit()
            except Exception as e:
                logger.warning("Aspen Quit() failed during cleanup: %s", e)

    if not keep_alive:
        # Delete temp INP if provided
        if inp_path and os.path.exists(inp_path):
            try:
                os.remove(inp_path)
            except OSError:
                pass
        
        # Remove Aspen artifacts from output_dir
        extensions = ['.bkp', '.apw', '.def', '.his', '.appdf']
        if os.path.exists(output_dir):
            for f in os.listdir(output_dir):
                if f == "compiled_from_inp.bkp":
                    continue
                if any(f.endswith(ext) for ext in extensions):
                    try:
                        os.remove(os.path.join(output_dir, f))
                    except:
                        pass

def run_simulation_session(
    spec: Union[PlantSpecification, Dict[str, Any], str],
    build_mode: str = "auto",
    output_dir: str = "results/",
    visible: bool = True,
    timeout_seconds: int = 300,
    build_timeout_seconds: int = DEFAULT_BUILD_TIMEOUT_SECONDS,
    keep_alive: bool = False,
    raise_on_connection_error: bool = False
) -> SessionResult:
    """
    Orchestrates the simulation session.

    Args:
        spec: A :class:`PlantSpecification` object, a dict representation of
            one, or a path string to a YAML/JSON spec file.
        raise_on_connection_error: If True, re-raises AspenConnectionError
            instead of returning a soft-failed SessionResult.
    """
    result = SessionResult()

    # --- Comment 1: branch on spec type ---
    if isinstance(spec, str):
        # File path -> load and validate
        spec = load_spec(spec)
    elif isinstance(spec, dict):
        # Raw dict -> validate then construct
        report = validate_spec(spec)
        if not report["valid"]:
            raise ValueError(f"Invalid spec dict: {report['errors']}")
        spec = PlantSpecification(**spec)
    elif isinstance(spec, PlantSpecification):
        # Already a model instance -> still validate
        report = validate_spec(spec.model_dump())
        if not report["valid"]:
            raise ValueError(f"Invalid PlantSpecification: {report['errors']}")
    else:
        raise TypeError(f"spec must be a PlantSpecification, dict, or file path str; got {type(spec).__name__}")

    # Validate build_mode format
    valid_modes = ["auto", "inp-only", "com-only", "com-auto"]
    if build_mode not in valid_modes:
        raise ValueError(f"Invalid build_mode '{build_mode}'. Must be one of {valid_modes}")

    start_time = time.time()
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    # Use a generic name as per plan (temp INP)
    inp_filename = "temp_simulation.inp"
    inp_path = os.path.join(output_dir, inp_filename)
    
    if not check_aspen_running():
        raise AspenNotRunningError()

    aspen = None
    force_cleanup = False
    try:
        # Connect
        aspen = _connect_aspen()
        result.aspen = aspen

        preflight = _verify_aspen_v14_connection(aspen, visible=visible, suppress_dialogs=True)
        preflight["dispatch_mode"] = _LAST_DISPATCH_MODE
        if _LAST_DISPATCH_FALLBACK_ERROR:
            preflight["dispatch_ex_error"] = _LAST_DISPATCH_FALLBACK_ERROR
        result.diagnostics["aspen_preflight"] = preflight
        result.diagnostics["aspen_version"] = preflight.get("aspen_version")
        result.diagnostics["v14_verified"] = preflight.get("v14_verified")
        result.diagnostics["v14_version_verified"] = preflight.get("v14_version_verified")
        result.diagnostics["aspen_connection_verified"] = preflight.get("connection_verified")
        result.diagnostics["dispatch_mode"] = _LAST_DISPATCH_MODE
        if _LAST_DISPATCH_FALLBACK_ERROR:
            result.diagnostics["dispatch_ex_error"] = _LAST_DISPATCH_FALLBACK_ERROR
        
        # Build
        if build_mode == "auto":
            _build_auto(
                spec,
                inp_path,
                aspen,
                result,
                visible=visible,
                suppress_dialogs=True,
                build_timeout_seconds=build_timeout_seconds,
            )
        elif build_mode == "inp-only":
            result.build_mode = "inp-only"
            _build_inp_only(spec, inp_path, aspen, result=result, visible=visible, suppress_dialogs=True)
            result.build_mechanism_used = "InitFromFile2"
            result.diagnostics["build_mechanism"] = "InitFromFile2"
        elif build_mode == "com-only":
            result.build_mode = "com-only"
            _build_com_only(spec, aspen, result, visible=visible, suppress_dialogs=True)
        elif build_mode == "com-auto":
            _build_com_auto(
                spec,
                inp_path,
                aspen,
                result,
                visible=visible,
                suppress_dialogs=True,
                build_timeout_seconds=build_timeout_seconds,
            )
            
        # Run
        block_names = [block.name for block in spec.blocks]
        status, sim_time, messages, simulation_diagnostics = _run_simulation(
            aspen,
            timeout=timeout_seconds,
            block_names=block_names,
        )
        result.convergence_status = status
        result.simulation_time_seconds = sim_time
        result.status_messages = messages
        result.diagnostics.update(simulation_diagnostics)
        
        if status == "converged":
            log("Simulation converged successfully.")
        elif status == "timeout":
            log("Simulation timed out.")
        else:
            log(f"Simulation failed to converge. Errors found: {len(messages)}")
            for msg in messages[:5]: # Log first few
                 log(f"  Aspen: {msg.strip()}", level="WARNING")
        
    except (ValueError, TypeError):
        # Re-raise argument errors immediately
        force_cleanup = True
        raise
    except AspenConnectionError as e:
        force_cleanup = True
        if raise_on_connection_error:
            raise
        log(f"Connection Error: {e}", level="ERROR")
        result.diagnostics["error"] = str(e)
        result.diagnostics["connection_error_type"] = type(e).__name__
        if isinstance(getattr(e, "details", None), dict):
            preflight = dict(e.details)
            result.diagnostics["aspen_preflight"] = preflight
            result.diagnostics["aspen_version"] = preflight.get("aspen_version")
            result.diagnostics["v14_verified"] = preflight.get("v14_verified")
            result.diagnostics["v14_version_verified"] = preflight.get("v14_version_verified")
            result.diagnostics["aspen_connection_verified"] = preflight.get("connection_verified")
        result.convergence_status = "failed"
    except BuildError as e:
        # --- Comment 2: re-raise BuildError so callers see it ---
        log(f"Build Error: {e}", level="ERROR")
        force_cleanup = True
        raise
    except SimulationError as e:
        force_cleanup = True
        log(f"Simulation Error: {e}", level="ERROR")
        result.diagnostics["error"] = str(e)
        result.convergence_status = e.convergence_status
    except Exception as e:
        force_cleanup = True
        log(f"Unexpected Error: {e}", level="ERROR")
        result.diagnostics["error"] = f"Unexpected error: {e}"
        result.convergence_status = "failed"
    finally:
        effective_keep_alive = keep_alive and not force_cleanup
        _cleanup_session(aspen, output_dir, inp_path, effective_keep_alive)
        if not effective_keep_alive:
            result.aspen = None
        
    return result
