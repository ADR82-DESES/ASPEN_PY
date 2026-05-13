from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

import pandas as pd

from .acceptance import validate_acceptance
from .batch_engine import AspenBatchResult, run_aspen_batch
from .capsule_context import collect_capsule_context
from .exceptions import AspenNotRunningError, BuildError, ExtractionError, ValidationError
from .extractor import extract_results
from .inp_generator import generate_inp
from .parser import load_spec
from .process_spec_coherence import (
    analyze_process_spec_coherence,
    apply_process_spec_improvements,
    dump_process_spec_yaml,
    suggest_process_spec_improvements,
)
from .reporter import generate_reports
from .serialization import spec_to_plain_dict
from .session import (
    SessionResult,
    _cleanup_session,
    _connect_aspen,
    _initialize_aspen_props,
    _run_simulation,
    check_aspen_running,
    run_simulation_session,
)
from .validator import validate_spec


@dataclass(frozen=True)
class ProcessDefinition:
    name: str
    process_dir: Path
    spec_path: Path


@dataclass(frozen=True)
class ProcessIssue:
    process_name: str
    process_dir: Path
    message: str


@dataclass(frozen=True)
class ProcessLibraryScan:
    library_root: Path
    processes: list[ProcessDefinition]
    issues: list[ProcessIssue]


@dataclass(frozen=True)
class ProcessLayout:
    process_root: Path
    run_dir: Path
    generated_inp_path: Path
    output_apw_path: Path
    results_dir: Path
    reports_root: Path
    session_dir: Path


@dataclass
class ProcessRunResult:
    process_name: str
    process_dir: Path
    spec_path: Path | None
    status: str
    validation_report: dict[str, Any] | None = None
    layout: ProcessLayout | None = None
    report_dir: Path | None = None
    generated_files: list[str] = field(default_factory=list)
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.status == "succeeded"

    def to_summary_row(self) -> dict[str, Any]:
        return {
            "process_name": self.process_name,
            "status": self.status,
            "spec_path": str(self.spec_path) if self.spec_path else "",
            "report_dir": str(self.report_dir) if self.report_dir else "",
            "error": self.error or "",
        }


@dataclass
class BkpExtractionResult:
    session_result: SessionResult
    results: dict[str, Any]
    context_probe: dict[str, Any]


def _resolve_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _slugify_process_name(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    return slug or "process"


def _timestamp() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _resolve_process_spec_path(process_dir: Path) -> Path:
    canonical = process_dir / "process.yaml"
    if canonical.is_file():
        return canonical

    candidates = sorted(
        path
        for path in process_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".yaml", ".yml"}
    )
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise FileNotFoundError("No YAML specification found. Add process.yaml to the process folder.")
    raise ValueError("Multiple YAML files found without a canonical process.yaml. Keep only one YAML file or rename the intended spec to process.yaml.")


def _build_layout(process_name: str, runs_root: Path) -> ProcessLayout:
    process_slug = _slugify_process_name(process_name)
    process_root = runs_root / process_name
    run_dir = process_root / f"run_{_timestamp()}"
    return ProcessLayout(
        process_root=process_root,
        run_dir=run_dir,
        generated_inp_path=run_dir / f"{process_slug}_generated.inp",
        output_apw_path=run_dir / f"{process_slug}_output.apw",
        results_dir=run_dir / "results",
        reports_root=run_dir / "reports",
        session_dir=run_dir / "session",
    )


def _ensure_layout_dirs(layout: ProcessLayout) -> None:
    layout.run_dir.mkdir(parents=True, exist_ok=True)
    layout.results_dir.mkdir(parents=True, exist_ok=True)
    layout.reports_root.mkdir(parents=True, exist_ok=True)
    layout.session_dir.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _write_process_results(
    results: dict[str, Any],
    results_dir: Path,
    simulation_time_seconds: float,
    acceptance: dict[str, Any],
) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)

    streams = results.get("streams")
    if streams is not None and hasattr(streams, "to_csv"):
        streams.to_csv(results_dir / "streams.csv", index=False)

    blocks = results.get("blocks")
    if blocks is not None and hasattr(blocks, "to_csv"):
        blocks.to_csv(results_dir / "blocks.csv", index=False)

    material_balance = results.get("material_balance")
    if material_balance is not None and hasattr(material_balance, "to_csv"):
        material_balance.to_csv(results_dir / "material_balance.csv", index=False)

    energy_balance = results.get("energy_balance")
    if energy_balance is not None and hasattr(energy_balance, "to_csv"):
        energy_balance.to_csv(results_dir / "energy_balance.csv", index=False)

    kpis = results.get("kpis")
    if not isinstance(kpis, dict):
        kpis = {}
    else:
        kpis = dict(kpis)
    kpis["simulation_time_seconds"] = simulation_time_seconds
    _write_json(results_dir / "kpis.json", kpis)
    diagnostics = results.get("diagnostics")
    _write_json(results_dir / "diagnostics.json", diagnostics if isinstance(diagnostics, dict) else {})
    _write_json(results_dir / "acceptance.json", acceptance)


def _collect_generated_files(root: Path) -> list[str]:
    return sorted(str(path.relative_to(root)) for path in root.rglob("*") if path.is_file())


def _build_diagnostics_payload(
    *,
    session_result: Any | None = None,
    build_error: BuildError | None = None,
) -> dict[str, Any]:
    diagnostics = dict(getattr(session_result, "diagnostics", {}) if session_result is not None else {})
    if build_error is not None:
        diagnostics.update(dict(build_error.diagnostics))

    verification = diagnostics.get("flowsheet_verification", {})
    if not isinstance(verification, dict):
        verification = {}

    build_valid = verification.get("build_valid", diagnostics.get("build_valid"))
    session_status = str(getattr(session_result, "convergence_status", "") or "").strip().lower()
    preflight = diagnostics.get("aspen_preflight", {})
    if not isinstance(preflight, dict):
        preflight = {}
    connection_failed = bool(
        build_error is None
        and session_result is not None
        and session_status == "failed"
        and (
            diagnostics.get("connection_error_type")
            or (
                preflight
                and not preflight.get("connection_verified", diagnostics.get("aspen_connection_verified", False))
            )
        )
    )
    if connection_failed and build_valid is None:
        build_valid = False

    issues: list[str] = []
    if build_error is not None:
        issues.append(str(build_error))
        batch_engine = diagnostics.get("batch_engine")
        if isinstance(batch_engine, dict):
            history = batch_engine.get("history_diagnostics")
            if isinstance(history, dict):
                for message in history.get("messages", [])[:5]:
                    if isinstance(message, dict) and message.get("message"):
                        issues.append(str(message["message"]))
    elif connection_failed:
        issues.append(str(diagnostics.get("error") or "Aspen connection/preflight failed."))
    elif build_valid is False:
        issues.append("Aspen build verification did not confirm populated stream and block trees.")

    if connection_failed:
        status = "connection_failed"
    elif build_error is not None:
        status = "build_failed"
    elif build_valid is True:
        status = "build_verified"
    elif build_valid is False:
        status = "build_invalid"
    else:
        status = "build_unverified"

    return {
        "passed": status == "build_verified",
        "status": status,
        "build_valid": build_valid,
        "build_mode": build_error.build_mode if build_error is not None else getattr(session_result, "build_mode", None),
        "build_mechanism_used": (
            build_error.mechanism_tried if build_error is not None else getattr(session_result, "build_mechanism_used", None)
        ),
        "generated_inp_path": diagnostics.get("generated_inp_path"),
        "flowsheet_verification": verification,
        "diagnostics": diagnostics,
        "issues": issues,
    }


def _coherence_error_count(coherence_report: dict[str, Any]) -> int:
    return sum(1 for issue in coherence_report.get("issues", []) if issue.get("severity") == "error")


def _is_missing_scalar(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except Exception:
        return False


def _required_kpi_names(spec: dict[str, Any]) -> list[str]:
    targets = spec.get("targets", {})
    if not isinstance(targets, dict):
        return []

    required: list[str] = []
    if targets.get("production_rate_tpd") is not None:
        required.append("production_rate_tpd")

    purity = targets.get("purity", {})
    if isinstance(purity, dict) and purity.get("min_value") is not None:
        required.append("purity_fraction")

    return required


def _numeric_row_count(table: Any, *, exclude_columns: set[str]) -> int:
    if not isinstance(table, pd.DataFrame) or table.empty:
        return 0

    value_columns = [column for column in table.columns if column not in exclude_columns]
    if not value_columns:
        return 0

    numeric_values = table[value_columns].apply(pd.to_numeric, errors="coerce")
    if numeric_values.empty:
        return 0

    return int(numeric_values.notna().any(axis=1).sum())


def _failed_acceptance_checks(acceptance: dict[str, Any]) -> set[str]:
    failed: set[str] = set()
    for check in acceptance.get("checks", []):
        if isinstance(check, dict) and not check.get("passed"):
            failed.add(str(check.get("name", "")))
    return failed


def _build_simulation_diagnostics(
    spec: dict[str, Any],
    session_result: Any,
    results: dict[str, Any],
    acceptance: dict[str, Any],
    *,
    enforce_acceptance_targets: bool = True,
    require_balance_tables: bool = False,
) -> dict[str, Any]:
    session_status = str(getattr(session_result, "convergence_status", "unknown") or "unknown").strip().lower()
    session_diagnostics = dict(getattr(session_result, "diagnostics", {}))
    flowsheet_verification = session_diagnostics.get("flowsheet_verification", {})
    if not isinstance(flowsheet_verification, dict):
        flowsheet_verification = {}
    build_valid = flowsheet_verification.get("build_valid", session_diagnostics.get("build_valid"))

    extraction_diagnostics = results.get("diagnostics", {})
    extraction_diagnostics = extraction_diagnostics if isinstance(extraction_diagnostics, dict) else {}
    extraction_status = str(extraction_diagnostics.get("convergence_status", "unknown") or "unknown").strip().lower()

    stream_numeric_rows = _numeric_row_count(results.get("streams"), exclude_columns={"stream_name"})
    block_numeric_rows = _numeric_row_count(results.get("blocks"), exclude_columns={"block_name", "block_type"})
    material_balance_rows = _numeric_row_count(results.get("material_balance"), exclude_columns={"component"})
    energy_balance_rows = _numeric_row_count(results.get("energy_balance"), exclude_columns={"block_name"})

    kpis = results.get("kpis", {})
    kpis = kpis if isinstance(kpis, dict) else {}
    required_kpis = _required_kpi_names(spec) if enforce_acceptance_targets else []
    missing_required_kpis = [name for name in required_kpis if _is_missing_scalar(kpis.get(name))]
    missing_balance_tables: list[str] = []
    if require_balance_tables and material_balance_rows == 0:
        missing_balance_tables.append("material_balance")
    if require_balance_tables and energy_balance_rows == 0:
        missing_balance_tables.append("energy_balance")

    issues: list[str] = []
    if build_valid is False:
        issues.append("Aspen build verification did not confirm populated stream and block trees.")
    if session_status != "converged":
        issues.append(f"Session convergence status was '{session_status}'.")
    if extraction_status != "converged":
        issues.append(
            "Extracted Aspen diagnostics did not confirm convergence "
            f"(reported '{extraction_status}')."
        )
    if stream_numeric_rows == 0:
        issues.append("No numeric stream outputs were extracted from Aspen.")
    if block_numeric_rows == 0:
        issues.append("No numeric block outputs were extracted from Aspen.")
    if "material_balance" in missing_balance_tables:
        issues.append("No numeric material balance outputs were extracted from Aspen.")
    if "energy_balance" in missing_balance_tables:
        issues.append("No numeric energy balance outputs were extracted from Aspen.")
    for kpi_name in missing_required_kpis:
        issues.append(f"Required KPI '{kpi_name}' is missing from extracted results.")

    if (
        session_status == "converged"
        and stream_numeric_rows == 0
        and block_numeric_rows == 0
        and session_diagnostics.get("per_error") == 0
    ):
        issues.append("Convergence metadata was present, but the flowsheet appeared empty or unbuilt.")

    if stream_numeric_rows == 0 and block_numeric_rows == 0:
        results_status = "unreadable"
    elif stream_numeric_rows == 0 or block_numeric_rows == 0 or missing_required_kpis or missing_balance_tables:
        results_status = "incomplete"
    elif enforce_acceptance_targets and not acceptance.get("passed", False):
        results_status = "readable_acceptance_failed"
    else:
        results_status = "readable"

    if build_valid is False:
        status = "build_failed"
    elif session_status != "converged":
        status = "simulation_failed"
    elif extraction_status != "converged":
        status = "results_unreadable" if stream_numeric_rows == 0 and block_numeric_rows == 0 else "results_incomplete"
    elif stream_numeric_rows == 0 and block_numeric_rows == 0:
        status = "results_unreadable"
    elif stream_numeric_rows == 0 or block_numeric_rows == 0 or missing_required_kpis or missing_balance_tables:
        status = "results_incomplete"
    elif enforce_acceptance_targets and not acceptance.get("passed", False):
        status = "acceptance_failed"
    else:
        status = "succeeded"

    if status == "build_failed":
        summary = "Aspen build verification failed before usable result extraction."
    elif status == "simulation_failed":
        summary = "Aspen did not report a converged simulation session."
    elif status == "results_unreadable":
        summary = "Aspen session completed, but result nodes could not be read into usable outputs."
    elif status == "results_incomplete":
        summary = "Aspen produced partial outputs, but the run is missing required result coverage or KPIs."
    elif status == "acceptance_failed":
        summary = "Simulation ran and extracted successfully, but it did not meet the declared acceptance criteria."
    elif not enforce_acceptance_targets:
        summary = "Simulation outputs are readable; process acceptance targets were recorded but not enforced."
    else:
        summary = "Simulation outputs are readable and satisfy the declared acceptance criteria."

    return {
        "passed": status == "succeeded",
        "status": status,
        "summary": summary,
        "build_valid": build_valid,
        "run_status": session_status,
        "results_status": results_status,
        "session_convergence_status": session_status,
        "extraction_convergence_status": extraction_status,
        "simulation_time_seconds": getattr(session_result, "simulation_time_seconds", None),
        "stream_numeric_rows": stream_numeric_rows,
        "block_numeric_rows": block_numeric_rows,
        "material_balance_numeric_rows": material_balance_rows,
        "energy_balance_numeric_rows": energy_balance_rows,
        "required_balance_tables": bool(require_balance_tables),
        "missing_balance_tables": missing_balance_tables,
        "required_kpis": required_kpis,
        "missing_required_kpis": missing_required_kpis,
        "acceptance_targets_enforced": bool(enforce_acceptance_targets),
        "failed_acceptance_checks": sorted(_failed_acceptance_checks(acceptance)),
        "flowsheet_verification": flowsheet_verification,
        "session_diagnostics": session_diagnostics,
        "extraction_diagnostics": extraction_diagnostics,
        "issues": issues,
    }


def _build_yaml_update_artifacts(
    layout: ProcessLayout,
    spec: dict[str, Any],
    coherence_report: dict[str, Any],
    simulation_diagnostics: dict[str, Any],
    acceptance: dict[str, Any],
) -> dict[str, Any]:
    suggestions = suggest_process_spec_improvements(spec, coherence_report)
    failed_checks = set(simulation_diagnostics.get("failed_acceptance_checks", []))
    missing_required_kpis = set(simulation_diagnostics.get("missing_required_kpis", []))

    safe_suggestions: list[dict[str, Any]] = []
    manual_review_items = [suggestion for suggestion in suggestions if not suggestion.get("auto_applicable")]

    can_apply_safe_updates = bool(missing_required_kpis or failed_checks) and simulation_diagnostics.get("status") in {
        "results_incomplete",
        "acceptance_failed",
    }

    if can_apply_safe_updates:
        for suggestion in suggestions:
            if not suggestion.get("auto_applicable"):
                continue

            suggestion_id = str(suggestion.get("id", ""))
            if suggestion_id == "add_explicit_databanks":
                safe_suggestions.append(suggestion)
                continue

            if suggestion_id == "switch_property_method_to_nrtl" and (
                "Methanol Purity" in failed_checks or "purity_fraction" in missing_required_kpis
            ):
                safe_suggestions.append(suggestion)

    artifact: dict[str, Any] = {
        "status": simulation_diagnostics.get("status"),
        "generated_yaml": False,
        "proposal_path": None,
        "safe_suggestions": safe_suggestions,
        "manual_review_items": manual_review_items,
        "applied_suggestion_ids": [],
    }

    if safe_suggestions:
        selected_ids = [str(suggestion["id"]) for suggestion in safe_suggestions]
        proposed_spec, applied = apply_process_spec_improvements(spec, suggestions, selected_ids=selected_ids)
        proposal_path = layout.results_dir / "process_update_proposal.yaml"
        proposal_path.write_text(dump_process_spec_yaml(proposed_spec), encoding="utf-8")
        artifact["generated_yaml"] = True
        artifact["proposal_path"] = str(proposal_path)
        artifact["applied_suggestion_ids"] = [str(suggestion["id"]) for suggestion in applied]

    _write_json(layout.results_dir / "yaml_update_suggestions.json", artifact)
    return artifact


def discover_processes(library_root: str | Path) -> list[ProcessDefinition]:
    return scan_process_library(library_root).processes


def scan_process_library(library_root: str | Path) -> ProcessLibraryScan:
    root = _resolve_path(library_root)
    processes: list[ProcessDefinition] = []
    issues: list[ProcessIssue] = []

    if not root.exists():
        issues.append(
            ProcessIssue(
                process_name=root.name or "process_library",
                process_dir=root,
                message=f"Process library does not exist: {root}",
            )
        )
        return ProcessLibraryScan(library_root=root, processes=processes, issues=issues)

    if not root.is_dir():
        issues.append(
            ProcessIssue(
                process_name=root.name,
                process_dir=root,
                message=f"Process library path is not a directory: {root}",
            )
        )
        return ProcessLibraryScan(library_root=root, processes=processes, issues=issues)

    for process_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        try:
            spec_path = _resolve_process_spec_path(process_dir)
        except (FileNotFoundError, ValueError) as exc:
            issues.append(
                ProcessIssue(
                    process_name=process_dir.name,
                    process_dir=process_dir,
                    message=str(exc),
                )
            )
            continue

        processes.append(
            ProcessDefinition(
                name=process_dir.name,
                process_dir=process_dir,
                spec_path=spec_path,
            )
        )

    return ProcessLibraryScan(library_root=root, processes=processes, issues=issues)


def load_process_spec(process_dir: str | Path) -> dict[str, Any]:
    process_path = _resolve_path(process_dir)
    spec_path = _resolve_process_spec_path(process_path)
    return load_spec(str(spec_path))


def validate_process_spec_file(process_yaml: str | Path) -> dict[str, Any]:
    spec_path = _resolve_path(process_yaml)
    spec = load_spec(str(spec_path), validate=False)
    report = validate_spec(spec)
    if not report.get("valid", False):
        return report

    try:
        generate_inp(spec)
    except ValidationError as exc:
        return exc.report

    return report


def _resolve_batch_first_spec_path(process_dir: Path, spec_path: str | Path | None = None) -> Path:
    canonical = _resolve_process_spec_path(process_dir).resolve()
    if spec_path is None:
        return canonical

    override = _resolve_path(spec_path)
    if override != canonical:
        raise ValueError(
            "Batch-first jobs use process_dir as the canonical input. "
            f"spec_path must resolve to the same file as {canonical}; got {override}."
        )
    return canonical


def _spec_block_names(spec: Any) -> list[str]:
    blocks = getattr(spec, "blocks", None)
    if blocks is None and isinstance(spec, dict):
        blocks = spec.get("blocks", [])
    names: list[str] = []
    for block in blocks or []:
        name = getattr(block, "name", None)
        if name is None and isinstance(block, dict):
            name = block.get("name")
        if name:
            names.append(str(name))
    return names


def _safe_collect_capsule_context(*, aspen: Any | None = None, engine_path: str | Path | None = None) -> dict[str, Any]:
    try:
        return collect_capsule_context(aspen=aspen, engine_path=engine_path)
    except Exception as exc:
        return {
            "status": "error",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def _write_context_probe(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(path, payload)


def _batch_history_issues(batch_result: AspenBatchResult) -> list[str]:
    issues: list[str] = []
    if batch_result.error:
        issues.append(str(batch_result.error))

    history = batch_result.history_diagnostics if isinstance(batch_result.history_diagnostics, dict) else {}
    history_status = str(history.get("status", "unknown") or "unknown")
    if history_status.lower() != "converged":
        issues.append(f"Aspen batch history status was '{history_status}'.")
    if history.get("input_translation_failed"):
        issues.append("Aspen history reported failed input translation.")

    for message in history.get("messages", [])[:5]:
        if isinstance(message, dict) and message.get("message"):
            issues.append(str(message["message"]))

    return issues


def _build_batch_first_diagnostics(batch_result: AspenBatchResult, generated_inp_path: Path) -> dict[str, Any]:
    status = "build_verified" if batch_result.succeeded else "batch_failed"
    return {
        "passed": batch_result.succeeded,
        "status": status,
        "build_valid": batch_result.succeeded,
        "build_mode": "batch-first",
        "build_mechanism_used": "aspen_batch",
        "generated_inp_path": str(generated_inp_path),
        "batch_archive_path": batch_result.archive_path,
        "history_diagnostics": batch_result.history_diagnostics,
        "batch_engine": batch_result.to_diagnostics(),
        "flowsheet_verification": {"build_valid": batch_result.succeeded},
        "diagnostics": {
            "batch_engine": batch_result.to_diagnostics(),
            "generated_inp_path": str(generated_inp_path),
        },
        "issues": _batch_history_issues(batch_result),
    }


def load_bkp_and_extract_results(
    spec: Any,
    bkp_path: str | Path,
    layout: ProcessLayout,
    *,
    visible: bool = False,
    timeout_seconds: int = 1800,
    context_probe_path: str | Path | None = None,
) -> BkpExtractionResult:
    archive_path = _resolve_path(bkp_path)
    if not archive_path.is_file():
        raise BuildError(
            f"Batch-created Aspen archive does not exist: {archive_path}",
            build_mode="batch-first",
            mechanism_tried="InitFromArchive2",
            diagnostics={"archive_path": str(archive_path)},
        )

    context_path = Path(context_probe_path) if context_probe_path is not None else layout.results_dir / "context_probe.json"
    aspen = None
    context_probe: dict[str, Any] = {}
    session_result = SessionResult(
        build_mode="batch-first",
        build_mechanism_used="InitFromArchive2",
    )

    try:
        if not check_aspen_running():
            raise AspenNotRunningError()

        aspen = _connect_aspen()
        session_result.aspen = aspen
        aspen.InitFromArchive2(str(archive_path))
        _initialize_aspen_props(aspen, visible=visible, suppress_dialogs=True)

        context_probe = _safe_collect_capsule_context(aspen=aspen)
        _write_context_probe(context_path, context_probe)

        session_result.diagnostics.update(
            {
                "build_valid": True,
                "build_mechanism": "batch_bkp_load",
                "archive_load_mechanism": "InitFromArchive2",
                "archive_path": str(archive_path),
                "context_probe_path": str(context_path),
                "flowsheet_verification": {"build_valid": True},
            }
        )

        status, sim_time, messages, simulation_diagnostics = _run_simulation(
            aspen,
            timeout=timeout_seconds,
            block_names=_spec_block_names(spec),
        )
        session_result.convergence_status = status
        session_result.simulation_time_seconds = sim_time
        session_result.status_messages = messages
        session_result.diagnostics.update(simulation_diagnostics)

        results: dict[str, Any] = {}
        if status == "converged":
            aspen.SaveAs(str(layout.output_apw_path))
            results = extract_results(aspen, spec)

        return BkpExtractionResult(
            session_result=session_result,
            results=results,
            context_probe=context_probe,
        )
    except Exception as exc:
        if not context_probe:
            context_probe = _safe_collect_capsule_context(aspen=aspen)
        context_probe["capsule_error"] = {
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        _write_context_probe(context_path, context_probe)
        raise
    finally:
        if aspen is not None:
            _cleanup_session(aspen, output_dir=str(layout.session_dir), keep_alive=False)
            session_result.aspen = None


def run_process_batch_first(
    process_dir: str | Path,
    runs_root: str | Path,
    *,
    visible: bool = False,
    enforce_acceptance_targets: bool = False,
    spec_path: str | Path | None = None,
    timeout_seconds: int = 1800,
    batch_timeout_seconds: int = 1800,
    report_format: str = "html",
    engine_path: str | None = None,
) -> ProcessRunResult:
    process_path = _resolve_path(process_dir)
    process_name = process_path.name

    try:
        resolved_spec_path = _resolve_batch_first_spec_path(process_path, spec_path=spec_path)
    except (FileNotFoundError, ValueError) as exc:
        return ProcessRunResult(
            process_name=process_name,
            process_dir=process_path,
            spec_path=None,
            status="discovery_failed",
            error=str(exc),
        )

    try:
        validation_report = validate_process_spec_file(resolved_spec_path)
    except Exception as exc:
        return ProcessRunResult(
            process_name=process_name,
            process_dir=process_path,
            spec_path=resolved_spec_path,
            status="validation_failed",
            error=str(exc),
        )

    if not validation_report.get("valid", False):
        return ProcessRunResult(
            process_name=process_name,
            process_dir=process_path,
            spec_path=resolved_spec_path,
            status="validation_failed",
            validation_report=validation_report,
            error=f"Validation failed with {len(validation_report.get('errors', []))} error(s).",
        )

    layout = _build_layout(process_name, _resolve_path(runs_root))
    _ensure_layout_dirs(layout)

    try:
        spec = load_spec(str(resolved_spec_path))
        plain_spec = spec_to_plain_dict(spec)
        coherence_report = analyze_process_spec_coherence(spec)
        _write_json(layout.results_dir / "coherence_report.json", coherence_report)
        if not coherence_report.get("passed", False):
            error_count = _coherence_error_count(coherence_report)
            return ProcessRunResult(
                process_name=process_name,
                process_dir=process_path,
                spec_path=resolved_spec_path,
                status="coherence_failed",
                validation_report=validation_report,
                layout=layout,
                generated_files=_collect_generated_files(layout.run_dir),
                error=f"Coherence analysis failed with {error_count} error(s).",
                details={"coherence": coherence_report},
            )

        generate_inp(spec, output_path=str(layout.generated_inp_path))
        batch_result = run_aspen_batch(
            layout.generated_inp_path,
            layout.session_dir / "batch",
            run_id=process_name,
            timeout_seconds=batch_timeout_seconds,
            engine_path=engine_path,
        )
        build_diagnostics = _build_batch_first_diagnostics(batch_result, layout.generated_inp_path)
        _write_json(layout.results_dir / "build_diagnostics.json", build_diagnostics)

        if not batch_result.succeeded:
            simulation_diagnostics = {
                "passed": False,
                "status": "batch_failed",
                "summary": "Aspen batch translation did not produce a clean converged archive.",
                "build_valid": False,
                "run_status": "not_started",
                "results_status": "not_extracted",
                "session_convergence_status": "not_started",
                "extraction_convergence_status": "not_started",
                "simulation_time_seconds": None,
                "flowsheet_verification": {"build_valid": False},
                "session_diagnostics": build_diagnostics.get("diagnostics", {}),
                "extraction_diagnostics": {},
                "issues": build_diagnostics.get("issues", []),
            }
            _write_json(layout.results_dir / "simulation_diagnostics.json", simulation_diagnostics)
            return ProcessRunResult(
                process_name=process_name,
                process_dir=process_path,
                spec_path=resolved_spec_path,
                status="batch_failed",
                validation_report=validation_report,
                layout=layout,
                generated_files=_collect_generated_files(layout.run_dir),
                error=simulation_diagnostics["summary"],
                details={
                    "build_diagnostics": build_diagnostics,
                    "coherence": coherence_report,
                    "simulation_diagnostics": simulation_diagnostics,
                    "batch_engine": batch_result.to_diagnostics(),
                },
            )

        extraction = load_bkp_and_extract_results(
            spec,
            str(batch_result.archive_path),
            layout,
            visible=visible,
            timeout_seconds=timeout_seconds,
            context_probe_path=layout.results_dir / "context_probe.json",
        )
        session_result = extraction.session_result
        build_diagnostics["build_mechanism_used"] = "aspen_batch+InitFromArchive2"
        build_diagnostics["archive_load_mechanism"] = "InitFromArchive2"
        build_diagnostics["context_probe_path"] = str(layout.results_dir / "context_probe.json")
        build_diagnostics["diagnostics"]["archive_load_mechanism"] = "InitFromArchive2"
        build_diagnostics["diagnostics"]["context_probe_path"] = str(layout.results_dir / "context_probe.json")
        _write_json(layout.results_dir / "build_diagnostics.json", build_diagnostics)

        status = str(session_result.convergence_status).strip().lower()
        if status != "converged":
            simulation_diagnostics = {
                "passed": False,
                "status": "simulation_failed",
                "summary": f"Simulation did not converge: {session_result.convergence_status!r}",
                "build_valid": build_diagnostics.get("build_valid"),
                "run_status": status,
                "results_status": "not_extracted",
                "session_convergence_status": session_result.convergence_status,
                "simulation_time_seconds": session_result.simulation_time_seconds,
                "session_diagnostics": dict(session_result.diagnostics),
                "flowsheet_verification": build_diagnostics.get("flowsheet_verification", {}),
                "issues": [f"Session convergence status was '{session_result.convergence_status}'."],
            }
            _write_json(layout.results_dir / "simulation_diagnostics.json", simulation_diagnostics)
            return ProcessRunResult(
                process_name=process_name,
                process_dir=process_path,
                spec_path=resolved_spec_path,
                status="simulation_failed",
                validation_report=validation_report,
                layout=layout,
                generated_files=_collect_generated_files(layout.run_dir),
                error=f"Simulation did not converge: {session_result.convergence_status!r}",
                details={
                    "build_diagnostics": build_diagnostics,
                    "coherence": coherence_report,
                    "simulation_diagnostics": simulation_diagnostics,
                    "batch_engine": batch_result.to_diagnostics(),
                    "context_probe": extraction.context_probe,
                    "convergence_status": session_result.convergence_status,
                    "simulation_time_seconds": session_result.simulation_time_seconds,
                    "diagnostics": dict(session_result.diagnostics),
                },
            )

        results = extraction.results
        acceptance = validate_acceptance(results, spec)
        results["acceptance"] = acceptance
        simulation_diagnostics = _build_simulation_diagnostics(
            plain_spec,
            session_result,
            results,
            acceptance,
            enforce_acceptance_targets=enforce_acceptance_targets,
            require_balance_tables=True,
        )
        yaml_update_artifacts = _build_yaml_update_artifacts(
            layout,
            plain_spec,
            coherence_report,
            simulation_diagnostics,
            acceptance,
        )

        _write_process_results(
            results,
            layout.results_dir,
            simulation_time_seconds=session_result.simulation_time_seconds,
            acceptance=acceptance,
        )
        _write_json(layout.results_dir / "simulation_diagnostics.json", simulation_diagnostics)
        report_dir = Path(
            generate_reports(
                results,
                spec,
                output_dir=str(layout.reports_root),
                format=report_format,
            )
        )

        common_details = {
            "build_diagnostics": build_diagnostics,
            "acceptance": acceptance,
            "coherence": coherence_report,
            "simulation_diagnostics": simulation_diagnostics,
            "yaml_update_artifacts": yaml_update_artifacts,
            "batch_engine": batch_result.to_diagnostics(),
            "context_probe": extraction.context_probe,
            "convergence_status": session_result.convergence_status,
            "simulation_time_seconds": session_result.simulation_time_seconds,
            "diagnostics": dict(session_result.diagnostics),
        }
        if not simulation_diagnostics.get("passed", False):
            return ProcessRunResult(
                process_name=process_name,
                process_dir=process_path,
                spec_path=resolved_spec_path,
                status=str(simulation_diagnostics.get("status", "failed")),
                validation_report=validation_report,
                layout=layout,
                report_dir=report_dir,
                generated_files=_collect_generated_files(layout.run_dir),
                error=str(simulation_diagnostics.get("summary", "Simulation output failed validation.")),
                details=common_details,
            )

        return ProcessRunResult(
            process_name=process_name,
            process_dir=process_path,
            spec_path=resolved_spec_path,
            status="succeeded",
            validation_report=validation_report,
            layout=layout,
            report_dir=report_dir,
            generated_files=_collect_generated_files(layout.run_dir),
            details=common_details,
        )
    except AspenNotRunningError as exc:
        context_probe = _safe_collect_capsule_context()
        context_probe["capsule_error"] = {"error_type": type(exc).__name__, "error": str(exc)}
        _write_context_probe(layout.results_dir / "context_probe.json", context_probe)
        simulation_diagnostics = {
            "passed": False,
            "status": "connection_failed",
            "summary": str(exc),
            "build_valid": False,
            "run_status": "not_started",
            "results_status": "not_extracted",
            "issues": [str(exc)],
            "context_probe_path": str(layout.results_dir / "context_probe.json"),
        }
        _write_json(layout.results_dir / "simulation_diagnostics.json", simulation_diagnostics)
        return ProcessRunResult(
            process_name=process_name,
            process_dir=process_path,
            spec_path=resolved_spec_path,
            status="connection_failed",
            validation_report=validation_report,
            layout=layout,
            generated_files=_collect_generated_files(layout.run_dir),
            error=str(exc),
            details={"simulation_diagnostics": simulation_diagnostics, "context_probe": context_probe},
        )
    except BuildError as exc:
        build_diagnostics = _build_diagnostics_payload(build_error=exc)
        _write_json(layout.results_dir / "build_diagnostics.json", build_diagnostics)
        _write_json(
            layout.results_dir / "simulation_diagnostics.json",
            {
                "passed": False,
                "status": "build_failed",
                "summary": "Batch-first BKP load failed before simulation run.",
                "build_valid": build_diagnostics.get("build_valid", False),
                "run_status": "not_started",
                "results_status": "not_extracted",
                "session_convergence_status": "not_started",
                "extraction_convergence_status": "not_started",
                "simulation_time_seconds": None,
                "flowsheet_verification": build_diagnostics.get("flowsheet_verification", {}),
                "session_diagnostics": build_diagnostics.get("diagnostics", {}),
                "extraction_diagnostics": {},
                "issues": build_diagnostics.get("issues", [str(exc)]),
            },
        )
        return ProcessRunResult(
            process_name=process_name,
            process_dir=process_path,
            spec_path=resolved_spec_path,
            status="build_failed",
            validation_report=validation_report,
            layout=layout,
            generated_files=_collect_generated_files(layout.run_dir),
            error=str(exc),
            details={"build_diagnostics": build_diagnostics},
        )
    except ExtractionError as exc:
        _write_json(
            layout.results_dir / "simulation_diagnostics.json",
            {
                "passed": False,
                "status": "results_unreadable",
                "summary": f"Result extraction failed: {exc}",
                "issues": [f"Result extraction failed: {exc}"],
            },
        )
        return ProcessRunResult(
            process_name=process_name,
            process_dir=process_path,
            spec_path=resolved_spec_path,
            status="results_unreadable",
            validation_report=validation_report,
            layout=layout,
            generated_files=_collect_generated_files(layout.run_dir),
            error=f"Result extraction failed: {exc}",
        )
    except Exception as exc:
        return ProcessRunResult(
            process_name=process_name,
            process_dir=process_path,
            spec_path=resolved_spec_path,
            status="failed",
            validation_report=validation_report,
            layout=layout,
            generated_files=_collect_generated_files(layout.run_dir),
            error=str(exc),
        )


def run_process(
    process_dir: str | Path,
    runs_root: str | Path,
    *,
    visible: bool = False,
    build_mode: str = "auto",
    timeout_seconds: int = 1800,
    build_timeout_seconds: int = 180,
    report_format: str = "html",
) -> ProcessRunResult:
    process_path = _resolve_path(process_dir)
    process_name = process_path.name

    try:
        spec_path = _resolve_process_spec_path(process_path)
    except (FileNotFoundError, ValueError) as exc:
        return ProcessRunResult(
            process_name=process_name,
            process_dir=process_path,
            spec_path=None,
            status="discovery_failed",
            error=str(exc),
        )

    try:
        validation_report = validate_process_spec_file(spec_path)
    except Exception as exc:
        return ProcessRunResult(
            process_name=process_name,
            process_dir=process_path,
            spec_path=spec_path,
            status="validation_failed",
            error=str(exc),
        )

    if not validation_report.get("valid", False):
        return ProcessRunResult(
            process_name=process_name,
            process_dir=process_path,
            spec_path=spec_path,
            status="validation_failed",
            validation_report=validation_report,
            error=f"Validation failed with {len(validation_report.get('errors', []))} error(s).",
        )

    layout = _build_layout(process_name, _resolve_path(runs_root))
    _ensure_layout_dirs(layout)

    aspen = None
    try:
        spec = load_spec(str(spec_path))
        plain_spec = spec_to_plain_dict(spec)
        coherence_report = analyze_process_spec_coherence(spec)
        _write_json(layout.results_dir / "coherence_report.json", coherence_report)
        if not coherence_report.get("passed", False):
            error_count = _coherence_error_count(coherence_report)
            return ProcessRunResult(
                process_name=process_name,
                process_dir=process_path,
                spec_path=spec_path,
                status="coherence_failed",
                validation_report=validation_report,
                layout=layout,
                generated_files=_collect_generated_files(layout.run_dir),
                error=f"Coherence analysis failed with {error_count} error(s).",
                details={"coherence": coherence_report},
            )

        generate_inp(spec, output_path=str(layout.generated_inp_path))

        session_result = run_simulation_session(
            spec,
            build_mode=build_mode,
            output_dir=str(layout.session_dir),
            keep_alive=True,
            timeout_seconds=timeout_seconds,
            build_timeout_seconds=build_timeout_seconds,
            visible=visible,
        )
        aspen = session_result.aspen

        if aspen is None:
            build_diagnostics = _build_diagnostics_payload(session_result=session_result)
            session_diagnostics = dict(session_result.diagnostics)
            error_message = str(
                session_diagnostics.get("error") or "Session did not return a live Aspen object."
            )
            diagnostic_status = str(build_diagnostics.get("status") or "").strip().lower()
            result_status = "connection_failed" if diagnostic_status == "connection_failed" else "session_failed"
            simulation_diagnostics = {
                "passed": False,
                "status": result_status,
                "summary": error_message,
                "build_valid": build_diagnostics.get("build_valid", False),
                "run_status": "not_started",
                "results_status": "not_extracted",
                "session_convergence_status": session_result.convergence_status,
                "simulation_time_seconds": session_result.simulation_time_seconds,
                "flowsheet_verification": build_diagnostics.get("flowsheet_verification", {}),
                "session_diagnostics": session_diagnostics,
                "extraction_diagnostics": {},
                "issues": build_diagnostics.get("issues", [error_message]),
            }
            _write_json(layout.results_dir / "build_diagnostics.json", build_diagnostics)
            _write_json(layout.results_dir / "simulation_diagnostics.json", simulation_diagnostics)
            return ProcessRunResult(
                process_name=process_name,
                process_dir=process_path,
                spec_path=spec_path,
                status=result_status,
                validation_report=validation_report,
                layout=layout,
                generated_files=_collect_generated_files(layout.run_dir),
                error=error_message,
                details={
                    "build_diagnostics": build_diagnostics,
                    "coherence": coherence_report,
                    "simulation_diagnostics": simulation_diagnostics,
                    "convergence_status": session_result.convergence_status,
                    "simulation_time_seconds": session_result.simulation_time_seconds,
                    "diagnostics": session_diagnostics,
                },
            )

        build_diagnostics = _build_diagnostics_payload(session_result=session_result)
        _write_json(layout.results_dir / "build_diagnostics.json", build_diagnostics)

        status = str(session_result.convergence_status).strip().lower()
        if status != "converged":
            simulation_diagnostics = {
                "passed": False,
                "status": "simulation_failed",
                "summary": f"Simulation did not converge: {session_result.convergence_status!r}",
                "build_valid": build_diagnostics.get("build_valid"),
                "run_status": status,
                "results_status": "not_extracted",
                "session_convergence_status": session_result.convergence_status,
                "simulation_time_seconds": session_result.simulation_time_seconds,
                "session_diagnostics": dict(session_result.diagnostics),
                "flowsheet_verification": build_diagnostics.get("flowsheet_verification", {}),
                "issues": [f"Session convergence status was '{session_result.convergence_status}'."],
            }
            _write_json(layout.results_dir / "simulation_diagnostics.json", simulation_diagnostics)
            return ProcessRunResult(
                process_name=process_name,
                process_dir=process_path,
                spec_path=spec_path,
                status="simulation_failed",
                validation_report=validation_report,
                layout=layout,
                error=f"Simulation did not converge: {session_result.convergence_status!r}",
                details={
                    "build_diagnostics": build_diagnostics,
                    "coherence": coherence_report,
                    "simulation_diagnostics": simulation_diagnostics,
                    "convergence_status": session_result.convergence_status,
                    "simulation_time_seconds": session_result.simulation_time_seconds,
                    "diagnostics": dict(session_result.diagnostics),
                },
            )

        aspen.SaveAs(str(layout.output_apw_path))

        results = extract_results(aspen, spec)
        acceptance = validate_acceptance(results, spec)
        results["acceptance"] = acceptance
        simulation_diagnostics = _build_simulation_diagnostics(plain_spec, session_result, results, acceptance)
        yaml_update_artifacts = _build_yaml_update_artifacts(
            layout,
            plain_spec,
            coherence_report,
            simulation_diagnostics,
            acceptance,
        )

        _write_process_results(
            results,
            layout.results_dir,
            simulation_time_seconds=session_result.simulation_time_seconds,
            acceptance=acceptance,
        )
        _write_json(layout.results_dir / "simulation_diagnostics.json", simulation_diagnostics)
        report_dir = Path(
            generate_reports(
                results,
                spec,
                output_dir=str(layout.reports_root),
                format=report_format,
            )
        )

        if not simulation_diagnostics.get("passed", False):
            return ProcessRunResult(
                process_name=process_name,
                process_dir=process_path,
                spec_path=spec_path,
                status=str(simulation_diagnostics.get("status", "failed")),
                validation_report=validation_report,
                layout=layout,
                report_dir=report_dir,
                generated_files=_collect_generated_files(layout.run_dir),
                error=str(simulation_diagnostics.get("summary", "Simulation output failed validation.")),
                details={
                    "build_diagnostics": build_diagnostics,
                    "acceptance": acceptance,
                    "coherence": coherence_report,
                    "simulation_diagnostics": simulation_diagnostics,
                    "yaml_update_artifacts": yaml_update_artifacts,
                    "convergence_status": session_result.convergence_status,
                    "simulation_time_seconds": session_result.simulation_time_seconds,
                    "diagnostics": dict(session_result.diagnostics),
                },
            )

        return ProcessRunResult(
            process_name=process_name,
            process_dir=process_path,
            spec_path=spec_path,
            status="succeeded",
            validation_report=validation_report,
            layout=layout,
            report_dir=report_dir,
            generated_files=_collect_generated_files(layout.run_dir),
            details={
                "build_diagnostics": build_diagnostics,
                "acceptance": acceptance,
                "coherence": coherence_report,
                "simulation_diagnostics": simulation_diagnostics,
                "yaml_update_artifacts": yaml_update_artifacts,
                "convergence_status": session_result.convergence_status,
                "simulation_time_seconds": session_result.simulation_time_seconds,
                "diagnostics": dict(session_result.diagnostics),
            },
        )
    except ValidationError as exc:
        return ProcessRunResult(
            process_name=process_name,
            process_dir=process_path,
            spec_path=spec_path,
            status="validation_failed",
            validation_report=validation_report,
            layout=layout,
            error=str(exc),
        )
    except BuildError as exc:
        build_diagnostics = _build_diagnostics_payload(build_error=exc)
        if layout is not None:
            _write_json(layout.results_dir / "build_diagnostics.json", build_diagnostics)
            _write_json(
                layout.results_dir / "simulation_diagnostics.json",
                {
                    "passed": False,
                    "status": "build_failed",
                    "summary": "Aspen build failed before simulation run.",
                    "build_valid": build_diagnostics.get("build_valid", False),
                    "run_status": "not_started",
                    "results_status": "not_extracted",
                    "session_convergence_status": "not_started",
                    "extraction_convergence_status": "not_started",
                    "simulation_time_seconds": None,
                    "flowsheet_verification": build_diagnostics.get("flowsheet_verification", {}),
                    "session_diagnostics": build_diagnostics.get("diagnostics", {}),
                    "extraction_diagnostics": {},
                    "issues": build_diagnostics.get("issues", [str(exc)]),
                },
            )
        return ProcessRunResult(
            process_name=process_name,
            process_dir=process_path,
            spec_path=spec_path,
            status="build_failed",
            validation_report=validation_report,
            layout=layout,
            generated_files=_collect_generated_files(layout.run_dir) if layout is not None else [],
            error=str(exc),
            details={"build_diagnostics": build_diagnostics},
        )
    except ExtractionError as exc:
        if layout is not None:
            _write_json(
                layout.results_dir / "simulation_diagnostics.json",
                {
                    "passed": False,
                    "status": "results_unreadable",
                    "summary": f"Result extraction failed: {exc}",
                    "issues": [f"Result extraction failed: {exc}"],
                },
            )
        return ProcessRunResult(
            process_name=process_name,
            process_dir=process_path,
            spec_path=spec_path,
            status="results_unreadable",
            validation_report=validation_report,
            layout=layout,
            generated_files=_collect_generated_files(layout.run_dir),
            error=f"Result extraction failed: {exc}",
        )
    except Exception as exc:
        return ProcessRunResult(
            process_name=process_name,
            process_dir=process_path,
            spec_path=spec_path,
            status="failed",
            validation_report=validation_report,
            layout=layout,
            generated_files=_collect_generated_files(layout.run_dir),
            error=str(exc),
        )
    finally:
        if aspen is not None:
            _cleanup_session(aspen, output_dir=str(layout.session_dir), keep_alive=False)


def run_process_library(
    library_root: str | Path,
    runs_root: str | Path,
    *,
    visible: bool = False,
    build_mode: str = "auto",
    timeout_seconds: int = 1800,
    build_timeout_seconds: int = 180,
    report_format: str = "html",
    continue_on_error: bool = True,
) -> list[ProcessRunResult]:
    scan = scan_process_library(library_root)
    results: list[ProcessRunResult] = [
        ProcessRunResult(
            process_name=issue.process_name,
            process_dir=issue.process_dir,
            spec_path=None,
            status="discovery_failed",
            error=issue.message,
        )
        for issue in scan.issues
    ]

    for process in scan.processes:
        result = run_process(
            process.process_dir,
            runs_root,
            visible=visible,
            build_mode=build_mode,
            timeout_seconds=timeout_seconds,
            build_timeout_seconds=build_timeout_seconds,
            report_format=report_format,
        )
        results.append(result)

        if not continue_on_error and not result.succeeded:
            break

    return results


__all__ = [
    "BkpExtractionResult",
    "ProcessDefinition",
    "ProcessIssue",
    "ProcessLayout",
    "ProcessLibraryScan",
    "ProcessRunResult",
    "discover_processes",
    "scan_process_library",
    "load_process_spec",
    "load_bkp_and_extract_results",
    "validate_process_spec_file",
    "run_process",
    "run_process_batch_first",
    "run_process_library",
]
