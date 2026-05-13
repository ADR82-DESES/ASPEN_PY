from __future__ import annotations

from typing import Any, Optional, Sequence


RUN_STATUS_PATHS = [
    r"\Data\Convergence\Batch-Options\Output\PER_ERROR",
    r"\Data\Results Summary\Run-Status\Output\PER_ERROR",
    r"\Data\Convergence\Sequence\Batch-Options\Output\PER_ERROR",
    r"\Data\Results Summary\Convergence\Output\PER_ERROR",
]

ERROR_COUNT_PATHS = [
    r"\Data\Results Summary\Run-Status\Output\NERROR",
    r"\Data\Results Summary\Convergence\Output\NERROR",
]

WARNING_COUNT_PATHS = [
    r"\Data\Results Summary\Run-Status\Output\NWARN",
    r"\Data\Results Summary\Convergence\Output\NWARN",
]

MESSAGE_PATHS = [
    r"\Data\Results Summary\Run-Status\Output\MESSAGES",
    r"\Data\Results Summary\Convergence\Output\MESSAGES",
]


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get_node_value(aspen: Any, path: str) -> Optional[float]:
    try:
        node = aspen.Tree.FindNode(path)
        if node is None:
            return None
        return _as_float(node.Value)
    except Exception:
        return None


def _get_message_list(aspen: Any, path: str) -> Optional[list[str]]:
    try:
        node = aspen.Tree.FindNode(path)
        if node is None:
            return None
        value = node.Value
    except Exception:
        return None

    if value is None:
        return None
    if isinstance(value, str):
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        return lines or None
    if isinstance(value, (list, tuple)):
        lines = [str(item).strip() for item in value if str(item).strip()]
        return lines or None
    return [str(value).strip()] if str(value).strip() else None


def _first_numeric_value(aspen: Any, paths: Sequence[str]) -> tuple[Optional[float], Optional[str]]:
    for path in paths:
        value = _get_node_value(aspen, path)
        if value is not None:
            return value, path
    return None, None


def _normalize_block_names(block_names: Sequence[str] | None) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for block_name in block_names or []:
        if not block_name:
            continue
        text = str(block_name)
        key = text.upper()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)

    return normalized


def read_aspen_run_diagnostics(
    aspen: Any,
    *,
    block_names: Sequence[str] | None = None,
) -> dict[str, Any]:
    per_error, per_error_path = _first_numeric_value(aspen, RUN_STATUS_PATHS)
    error_count, error_count_path = _first_numeric_value(aspen, ERROR_COUNT_PATHS)
    warning_count, warning_count_path = _first_numeric_value(aspen, WARNING_COUNT_PATHS)

    messages: list[str] = []
    message_path: str | None = None
    for path in MESSAGE_PATHS:
        found = _get_message_list(aspen, path)
        if found:
            messages = found
            message_path = path
            break

    convergence_status = "unknown"
    status_source = "unresolved"

    if per_error is not None:
        convergence_status = "converged" if per_error == 0 else "failed"
        status_source = per_error_path or "per_error"
    else:
        for block_name in _normalize_block_names(block_names):
            block_status_path = rf"\Data\Blocks\{block_name}\Output\BLKSTAT"
            block_status = _get_node_value(aspen, block_status_path)
            if block_status is None:
                continue
            convergence_status = "converged" if block_status == 0 else "failed"
            status_source = block_status_path
            break

    return {
        "per_error": per_error,
        "per_error_path": per_error_path,
        "error_count": error_count,
        "error_count_path": error_count_path,
        "warning_count": warning_count,
        "warning_count_path": warning_count_path,
        "convergence_status": convergence_status,
        "status_source": status_source,
        "messages": messages,
        "message_path": message_path,
    }


__all__ = ["read_aspen_run_diagnostics"]
