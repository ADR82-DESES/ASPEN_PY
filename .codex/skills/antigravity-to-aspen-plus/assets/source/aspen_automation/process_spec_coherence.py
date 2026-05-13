from __future__ import annotations

import re
import shutil
from copy import deepcopy
import datetime as _dt
from pathlib import Path
from typing import Any

import yaml

from .serialization import spec_to_plain_dict
from .schema import PlantSpecification


PURITY_EXPRESSION_RE = re.compile(
    r"^\s*(?P<component>[A-Za-z0-9_.+-]+)\s+"
    r"(?P<basis>wt%|mass\s+fraction|mol%|mole\s+fraction)\s+in\s+"
    r"(?P<stream>[A-Za-z0-9_.+-]+)\s*$",
    re.IGNORECASE,
)

POLAR_METHANOL_METHOD_WARN = {"IDEAL", "RK-SOAVE", "PENG-ROB", "SRK"}
RIGOROUS_SEPARATION_TYPES = {"RADFRAC"}
SIMPLE_HIGH_PURITY_SEPARATION_TYPES = {"SEP", "FLASH2", "FSPLIT"}
DEFAULT_EXPLICIT_DATABANKS = [
    "APV140 PURE32",
    "APV140 AQUEOUS",
    "APV140 SOLIDS",
    "APV140 INORGANIC",
]


def _coerce_spec(spec: PlantSpecification | dict[str, Any]) -> PlantSpecification:
    if isinstance(spec, PlantSpecification):
        return spec
    if isinstance(spec, dict):
        return PlantSpecification(**spec)
    raise TypeError("spec must be a PlantSpecification or dict")


def _make_issue(severity: str, location: str, message: str, suggestion: str) -> dict[str, str]:
    return {
        "severity": severity,
        "location": location,
        "message": message,
        "suggestion": suggestion,
    }


def _find_block_output_mapping(spec: PlantSpecification) -> dict[str, tuple[int, str]]:
    output_to_block: dict[str, tuple[int, str]] = {}
    block_by_name = {block.name: block for block in spec.blocks}
    for index, connection in enumerate(spec.flowsheet):
        block = block_by_name.get(connection.block)
        block_type = block.type.upper() if block else "UNKNOWN"
        for output in connection.outputs:
            output_to_block[output] = (index, block_type)
    return output_to_block


def _format_issue_line(issue: dict[str, Any]) -> str:
    location = issue.get("location") or "unknown"
    message = issue.get("message") or "Unknown issue"
    suggestion = issue.get("suggestion") or ""
    if suggestion:
        return f"- `{location}`: {message} Suggestion: {suggestion}"
    return f"- `{location}`: {message}"


def _parse_purity_target(spec: PlantSpecification) -> tuple[str, str, str, float] | None:
    purity = spec.targets.purity if spec.targets and spec.targets.purity else None
    if purity is None:
        return None

    match = PURITY_EXPRESSION_RE.match(purity.expression)
    if not match:
        return None

    component_id = match.group("component").upper()
    stream_name = match.group("stream").upper()
    basis = "mass" if "wt" in match.group("basis").lower() or "mass" in match.group("basis").lower() else "mole"
    return component_id, stream_name, basis, purity.min_value


def _find_final_block_for_stream(spec: PlantSpecification, stream_name: str) -> tuple[int, Any] | None:
    normalized = stream_name.upper()
    block_by_name = {block.name: block for block in spec.blocks}
    for index, connection in enumerate(spec.flowsheet):
        if normalized in {output.upper() for output in connection.outputs}:
            block = block_by_name.get(connection.block)
            if block is not None:
                return index, block
    return None


def _has_issue(
    coherence_report: dict[str, Any] | None,
    *,
    severity: str | None = None,
    location: str | None = None,
    message_contains: str | None = None,
) -> bool:
    if not isinstance(coherence_report, dict):
        return False

    for issue in coherence_report.get("issues", []):
        if severity is not None and issue.get("severity") != severity:
            continue
        if location is not None and issue.get("location") != location:
            continue
        if message_contains is not None and message_contains not in str(issue.get("message", "")):
            continue
        return True
    return False


def analyze_process_spec_coherence(spec: PlantSpecification | dict[str, Any]) -> dict[str, Any]:
    spec_obj = _coerce_spec(spec)
    issues: list[dict[str, str]] = []

    component_ids = {component.id.upper() for component in spec_obj.components}
    stream_by_name = {stream.name.upper(): stream for stream in spec_obj.streams}
    block_by_name = {block.name: block for block in spec_obj.blocks}
    output_to_block = _find_block_output_mapping(spec_obj)

    if not spec_obj.properties.databanks:
        issues.append(
            _make_issue(
                "warning",
                "properties.databanks",
                "No explicit databanks are configured, so the run will fall back to defaults.",
                "Declare the databanks explicitly in YAML so the property environment is intentional and reproducible.",
            )
        )

    for index, block in enumerate(spec_obj.blocks):
        block_type = block.type.upper()

        if block_type == "FSPLIT" and block.split_fractions:
            split_total = sum(fraction.fraction for fraction in block.split_fractions)
            if abs(split_total - 1.0) > 1e-6:
                issues.append(
                    _make_issue(
                        "error",
                        f"blocks[{index}].split_fractions",
                        f"Split fractions sum to {split_total:.6f}, not 1.0.",
                        "Make the FSPLIT outlet fractions sum to exactly 1.0.",
                    )
                )

    purity_target = _parse_purity_target(spec_obj)
    if purity_target is not None:
        target_component, target_stream, target_basis, target_min = purity_target

        if target_component not in component_ids:
            issues.append(
                _make_issue(
                    "error",
                    "targets.purity.expression",
                    f"Purity target references component '{target_component}' which is not defined in components.",
                    f"Add component '{target_component}' or correct the purity expression.",
                )
            )
        if target_stream not in stream_by_name:
            issues.append(
                _make_issue(
                    "error",
                    "targets.purity.expression",
                    f"Purity target references stream '{target_stream}' which is not defined in streams.",
                    f"Add stream '{target_stream}' or correct the purity expression.",
                )
            )

        target_stream_spec = stream_by_name.get(target_stream)
        if target_stream_spec is not None and target_component in target_stream_spec.composition:
            target_fraction = float(target_stream_spec.composition[target_component])
            if target_fraction + 1e-9 < target_min:
                issues.append(
                    _make_issue(
                        "error",
                        f"streams[{target_stream_spec.name}].composition.{target_component}",
                        (
                            f"Nominal {target_basis}-based composition for stream '{target_stream_spec.name}' is "
                            f"{target_fraction:.6f}, below the purity target of {target_min:.6f}."
                        ),
                        "Raise the nominal product composition in YAML or relax the stated purity target.",
                    )
                )

        block_info = output_to_block.get(target_stream)
        if block_info is not None:
            _, final_block_type = block_info
            if target_min >= 0.99 and final_block_type in SIMPLE_HIGH_PURITY_SEPARATION_TYPES:
                issues.append(
                    _make_issue(
                        "warning",
                        "targets.purity",
                        (
                            f"High-purity target {target_min:.6f} for stream '{target_stream}' is delegated to a "
                            f"'{final_block_type}' block, which is a coarse screening model for final purification."
                        ),
                        (
                            "Keep this as a buildable screening model, or implement supported rigorous-column "
                            "generation before moving the final purification step to RADFRAC."
                        ),
                    )
                )

        method = spec_obj.properties.method.strip().upper()
        if (
            target_min >= 0.99
            and {"CH3OH", "H2O"}.issubset(component_ids)
            and method in POLAR_METHANOL_METHOD_WARN
        ):
            issues.append(
                _make_issue(
                    "warning",
                    "properties.method",
                    (
                        f"Property method '{spec_obj.properties.method}' is a weak choice for methanol/water "
                        "purification at high purity."
                    ),
                    "Use an activity-coefficient method such as NRTL or UNIQUAC for the purification section.",
                )
            )

    for index, block in enumerate(spec_obj.blocks):
        block_type = block.type.upper()
        if block_type not in {"REQUIL", "RGIBBS"}:
            continue
        synthesis_like = bool(block.reactions) or "SYN" in block.name.upper()
        if synthesis_like and "CH3OH" in component_ids:
            issues.append(
                _make_issue(
                    "warning",
                    f"blocks[{index}]",
                    (
                        f"Block '{block.name}' uses the equilibrium reactor model '{block_type}' for a methanol "
                        "synthesis step, which is only a coarse surrogate."
                    ),
                    "Use a kinetic reactor model for design-grade predictions, or keep this as a screening model only.",
                )
            )

    passed = not any(issue["severity"] == "error" for issue in issues)
    return {
        "passed": passed,
        "issues": issues,
    }


def suggest_process_spec_improvements(
    spec: PlantSpecification | dict[str, Any],
    coherence_report: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    spec_obj = _coerce_spec(spec)
    report = coherence_report if isinstance(coherence_report, dict) else analyze_process_spec_coherence(spec_obj)
    suggestions: list[dict[str, Any]] = []

    if _has_issue(report, severity="warning", location="properties.databanks"):
        suggestions.append(
            {
                "id": "add_explicit_databanks",
                "title": "Add explicit databanks",
                "auto_applicable": True,
                "reason": "The YAML is relying on fallback databanks, which makes the property environment implicit.",
                "expected_effect": "Removes the databank warning and makes the property setup reproducible.",
                "changes": [f"Set `properties.databanks` to {DEFAULT_EXPLICIT_DATABANKS!r}."],
            }
        )

    purity_target = _parse_purity_target(spec_obj)
    if purity_target is not None:
        _, target_stream, _, target_min = purity_target

        if _has_issue(report, severity="warning", location="properties.method"):
            suggestions.append(
                {
                    "id": "switch_property_method_to_nrtl",
                    "title": "Switch property method to NRTL",
                    "auto_applicable": True,
                    "reason": "The current method is weak for methanol/water purification near the declared purity target.",
                    "expected_effect": "Keeps the spec closer to a high-purity separation model.",
                    "changes": ["Change `properties.method` to `NRTL`."],
                }
            )

        final_block_info = _find_final_block_for_stream(spec_obj, target_stream)
        if (
            target_min >= 0.99
            and final_block_info is not None
            and _has_issue(report, location="targets.purity")
        ):
            _, final_block = final_block_info
            suggestions.append(
                {
                    "id": "upgrade_final_separator_to_radfrac",
                    "title": "Plan a supported RADFRAC upgrade",
                    "auto_applicable": False,
                    "reason": (
                        f"Stream `{target_stream}` is produced by `{final_block.name}`, currently typed as "
                        f"`{final_block.type}`, which is a coarse screening model for the high-purity target."
                    ),
                    "expected_effect": (
                        "Would improve purification rigor after the generator supports column stages, feeds, "
                        "condenser/reboiler settings, and product specifications."
                    ),
                    "changes": [
                        (
                            f"Do not auto-change `blocks[{final_block.name}].type` to `RADFRAC` until "
                            "generate_inp has a dedicated RADFRAC emitter."
                        )
                    ],
                }
            )

    if _has_issue(report, severity="warning", message_contains="equilibrium reactor model"):
        suggestions.append(
            {
                "id": "review_synthesis_reactor_model",
                "title": "Review the synthesis reactor model",
                "auto_applicable": False,
                "reason": "The synthesis loop is still modeled as an equilibrium reactor, which is only a screening approximation.",
                "expected_effect": "Would improve physical realism, but it needs engineering input rather than a blind YAML rewrite.",
                "changes": ["Consider replacing `B-SYN` with a kinetic reactor model and corresponding parameters."],
            }
        )

    return suggestions


def _apply_suggestion(spec_dict: dict[str, Any], suggestion_id: str) -> None:
    if suggestion_id == "add_explicit_databanks":
        spec_dict.setdefault("properties", {})["databanks"] = list(DEFAULT_EXPLICIT_DATABANKS)
        return

    if suggestion_id == "switch_property_method_to_nrtl":
        spec_dict.setdefault("properties", {})["method"] = "NRTL"
        return

    if suggestion_id == "upgrade_final_separator_to_radfrac":
        spec_obj = _coerce_spec(spec_dict)
        purity_target = _parse_purity_target(spec_obj)
        if purity_target is None:
            return
        _, target_stream, _, _ = purity_target
        final_block_info = _find_final_block_for_stream(spec_obj, target_stream)
        if final_block_info is None:
            return

        _, final_block = final_block_info
        for block in spec_dict.get("blocks", []):
            if str(block.get("name", "")).upper() == final_block.name.upper():
                block["type"] = "RADFRAC"
                break
        return


def apply_process_spec_improvements(
    spec: PlantSpecification | dict[str, Any],
    suggestions: list[dict[str, Any]],
    *,
    selected_ids: list[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    spec_obj = _coerce_spec(spec)
    updated_spec = deepcopy(spec_to_plain_dict(spec_obj))

    auto_suggestions = [suggestion for suggestion in suggestions if suggestion.get("auto_applicable")]
    if selected_ids is None:
        selected = auto_suggestions
    else:
        selected_set = set(selected_ids)
        selected = [suggestion for suggestion in auto_suggestions if suggestion["id"] in selected_set]

    for suggestion in selected:
        _apply_suggestion(updated_spec, suggestion["id"])

    return updated_spec, selected


def write_process_spec_file(
    spec_path: str | Path,
    spec_dict: dict[str, Any],
) -> Path:
    resolved_path = Path(spec_path).expanduser().resolve()
    if not resolved_path.is_file():
        raise FileNotFoundError(f"Spec file does not exist: {resolved_path}")

    backup_path = resolved_path.with_name(
        f"{resolved_path.stem}.bak_{_dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}{resolved_path.suffix}"
    )
    shutil.copy2(resolved_path, backup_path)
    resolved_path.write_text(dump_process_spec_yaml(spec_dict), encoding="utf-8")
    return backup_path


def dump_process_spec_yaml(spec: PlantSpecification | dict[str, Any]) -> str:
    return yaml.safe_dump(spec_to_plain_dict(spec), sort_keys=False, allow_unicode=False)


def build_codex_spec_markdown(
    process_name: str,
    spec_path: str | Path,
    validation_report: dict[str, Any] | None,
    coherence_report: dict[str, Any] | None,
    *,
    spec: PlantSpecification | dict[str, Any] | None = None,
) -> str:
    lines = [
        f"### Codex Session: YAML Coherence `{process_name}`",
        "",
        f"- Spec path: `{Path(spec_path)}`",
    ]

    spec_obj = _coerce_spec(spec) if spec is not None else None
    if spec_obj is not None:
        block_lineup = " -> ".join(block.name for block in spec_obj.blocks)
        lines.append(f"- Property method: `{spec_obj.properties.method}`")
        lines.append(f"- Block lineup: `{block_lineup}`")

    validation_errors = []
    if isinstance(validation_report, dict):
        validation_errors = list(validation_report.get("errors", []))
        lines.append(f"- Structural validation: {'passed' if validation_report.get('valid') else 'failed'}")

    if validation_errors:
        lines.append("")
        lines.append("Blocking validation issues:")
        lines.extend(_format_issue_line(issue) for issue in validation_errors)
        lines.append("- Execution gate: blocked until the structural validation issues are fixed.")
        return "\n".join(lines)

    if not isinstance(coherence_report, dict):
        lines.append("- Coherence analysis: unavailable")
        lines.append("- Execution gate: blocked until coherence analysis is available.")
        return "\n".join(lines)

    issues = list(coherence_report.get("issues", []))
    errors = [issue for issue in issues if issue.get("severity") == "error"]
    warnings = [issue for issue in issues if issue.get("severity") == "warning"]

    lines.append(f"- Coherence gate: {'passed' if coherence_report.get('passed') else 'blocked'}")

    if errors:
        lines.append("")
        lines.append("Why this did not pass the coherence test:")
        lines.extend(_format_issue_line(issue) for issue in errors)

    if warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(_format_issue_line(issue) for issue in warnings)

    if not errors and not warnings:
        lines.append("")
        lines.append("- No coherence issues were detected from the YAML-level checks.")

    lines.append("")
    if coherence_report.get("passed"):
        lines.append("- Execution gate: passed. The process can proceed to INP generation and Aspen execution.")
    else:
        lines.append("- Execution gate: blocked until the coherence errors are fixed.")

    return "\n".join(lines)


def build_codex_improvement_markdown(
    process_name: str,
    suggestions: list[dict[str, Any]],
) -> str:
    lines = [
        f"### Suggested YAML Improvements: `{process_name}`",
        "",
    ]

    if not suggestions:
        lines.append("- No YAML improvements were suggested.")
        return "\n".join(lines)

    auto_suggestions = [suggestion for suggestion in suggestions if suggestion.get("auto_applicable")]
    manual_suggestions = [suggestion for suggestion in suggestions if not suggestion.get("auto_applicable")]

    if auto_suggestions:
        lines.append("Automatic improvements available:")
        for index, suggestion in enumerate(auto_suggestions, start=1):
            lines.append(
                f"{index}. `{suggestion['title']}`: {suggestion['reason']} Expected effect: {suggestion['expected_effect']}"
            )
            for change in suggestion.get("changes", []):
                lines.append(f"   - {change}")
        lines.append("")
        lines.append(
            "Notebook prompt: enter `y` to apply all automatic improvements, `n` to skip, or a comma-separated list such as `1,3` to apply a subset."
        )

    if manual_suggestions:
        if auto_suggestions:
            lines.append("")
        lines.append("Additional manual review items:")
        for suggestion in manual_suggestions:
            lines.append(f"- `{suggestion['title']}`: {suggestion['reason']} Expected effect: {suggestion['expected_effect']}")

    return "\n".join(lines)


__all__ = [
    "analyze_process_spec_coherence",
    "suggest_process_spec_improvements",
    "apply_process_spec_improvements",
    "dump_process_spec_yaml",
    "write_process_spec_file",
    "build_codex_spec_markdown",
    "build_codex_improvement_markdown",
]
