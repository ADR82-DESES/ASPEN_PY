from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .schema import PlantSpecification

NRTL_ZERO_BINARY_WARNING_RE = re.compile(
    r"NRTL\s+BINARY\s+PARAMETERS.*ZERO|BINARY\s+PARAMETERS.*ZERO.*NRTL",
    re.IGNORECASE | re.DOTALL,
)

MODEL_QUALITY_WARNING_RE = re.compile(
    r"NRTL|BINARY\s+PARAMETER|PHYSICAL[-\s]+PROPERTY|PROPERTY\s+PARAMETER",
    re.IGNORECASE,
)

METHANOL_WATER_PAIR = ("CH3OH", "H2O")


def _plain_spec(spec: PlantSpecification | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(spec, PlantSpecification):
        return spec.model_dump(mode="json")
    if isinstance(spec, Mapping):
        return dict(spec)
    return {}


def normalize_component_pair(components: Any) -> tuple[str, str] | None:
    if not isinstance(components, (list, tuple)) or len(components) != 2:
        return None
    cleaned = []
    for component in components:
        if not isinstance(component, str) or not component.strip():
            return None
        cleaned.append(component.strip().upper())
    if cleaned[0] == cleaned[1]:
        return None
    return tuple(sorted(cleaned))


def _component_ids(spec: dict[str, Any]) -> set[str]:
    return {
        str(component.get("id", "")).strip().upper()
        for component in spec.get("components", [])
        if isinstance(component, Mapping)
    }


def _high_purity_methanol_water_required(spec: dict[str, Any]) -> bool:
    method = str(spec.get("properties", {}).get("method", "")).strip().upper()
    if method != "NRTL":
        return False
    if not set(METHANOL_WATER_PAIR).issubset(_component_ids(spec)):
        return False

    targets = spec.get("targets", {})
    purity = targets.get("purity", {}) if isinstance(targets, Mapping) else {}
    try:
        target_min = float(purity.get("min_value"))
    except (TypeError, ValueError):
        return False

    expression = str(purity.get("expression", "")).upper()
    return target_min >= 0.99 and "CH3OH" in expression


def required_nrtl_binary_pairs(spec: PlantSpecification | Mapping[str, Any]) -> list[tuple[str, str]]:
    plain = _plain_spec(spec)
    if _high_purity_methanol_water_required(plain):
        return [tuple(sorted(METHANOL_WATER_PAIR))]
    return []


def provided_nrtl_binary_pairs(spec: PlantSpecification | Mapping[str, Any]) -> list[tuple[str, str]]:
    plain = _plain_spec(spec)
    properties = plain.get("properties", {})
    if not isinstance(properties, Mapping):
        return []

    pairs: list[tuple[str, str]] = []
    for entry in properties.get("binary_parameters") or []:
        if not isinstance(entry, Mapping):
            continue
        if str(entry.get("model", "NRTL")).strip().upper() != "NRTL":
            continue
        pair = normalize_component_pair(entry.get("components"))
        if pair is not None:
            pairs.append(pair)
    return sorted(set(pairs))


def nrtl_binary_parameter_sources(spec: PlantSpecification | Mapping[str, Any]) -> list[dict[str, Any]]:
    plain = _plain_spec(spec)
    properties = plain.get("properties", {})
    if not isinstance(properties, Mapping):
        return []

    sources: list[dict[str, Any]] = []
    for entry in properties.get("binary_parameters") or []:
        if not isinstance(entry, Mapping):
            continue
        pair = normalize_component_pair(entry.get("components"))
        if pair is None:
            continue
        provenance = entry.get("provenance", {})
        provenance = dict(provenance) if isinstance(provenance, Mapping) else {}
        sources.append(
            {
                "components": list(pair),
                "model": str(entry.get("model", "NRTL")).strip().upper(),
                "source_type": entry.get("source_type", "aspen_databank"),
                "parameter_set": entry.get("parameter_set"),
                "databanks": list(entry.get("databanks") or []),
                "basis": entry.get("basis"),
                "provenance": provenance,
                "has_explicit_values": isinstance(entry.get("values"), Mapping) and bool(entry.get("values")),
            }
        )
    return sources


def history_has_nrtl_zero_binary_warning(history_diagnostics: Mapping[str, Any] | None) -> bool:
    if not isinstance(history_diagnostics, Mapping):
        return False
    for message in history_diagnostics.get("messages", []) or []:
        if not isinstance(message, Mapping):
            continue
        if NRTL_ZERO_BINARY_WARNING_RE.search(str(message.get("message", ""))):
            return True
    return False


def extract_model_quality_warnings(history_diagnostics: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(history_diagnostics, Mapping):
        return []

    warnings: list[str] = []
    for message in history_diagnostics.get("messages", []) or []:
        if not isinstance(message, Mapping):
            continue
        if str(message.get("severity", "")).strip().lower() != "warning":
            continue
        text = str(message.get("message", "")).strip()
        if text and MODEL_QUALITY_WARNING_RE.search(text):
            warnings.append(text)

    summary_counts = history_diagnostics.get("summary_counts", {})
    if isinstance(summary_counts, Mapping):
        physical_warnings = summary_counts.get("warnings", {})
        if isinstance(physical_warnings, Mapping):
            try:
                count = int(physical_warnings.get("physical_property") or 0)
            except (TypeError, ValueError):
                count = 0
            if count and not warnings:
                warnings.append(f"Aspen reported {count} physical-property warning(s) in the history file.")

    return warnings


def assess_nrtl_binary_parameters(
    spec: PlantSpecification | Mapping[str, Any],
    history_diagnostics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    plain = _plain_spec(spec)
    method = str(plain.get("properties", {}).get("method", "")).strip().upper()
    required_pairs = required_nrtl_binary_pairs(plain)
    provided_pairs = provided_nrtl_binary_pairs(plain)
    missing_pairs = sorted(set(required_pairs) - set(provided_pairs))
    history_status = str((history_diagnostics or {}).get("status", "")).strip().lower()
    zero_warning = history_has_nrtl_zero_binary_warning(history_diagnostics)

    if method != "NRTL":
        status = "not_applicable"
    elif zero_warning:
        status = "warning_from_aspen"
    elif missing_pairs:
        status = "missing"
    elif history_status == "converged":
        status = "accepted_by_aspen"
    elif provided_pairs:
        status = "provided"
    else:
        status = "not_required"

    return {
        "status": status,
        "method": method or None,
        "required_pairs": [list(pair) for pair in required_pairs],
        "provided_pairs": [list(pair) for pair in provided_pairs],
        "missing_pairs": [list(pair) for pair in missing_pairs],
        "zero_parameter_warning_present": zero_warning,
        "sources": nrtl_binary_parameter_sources(plain),
    }


__all__ = [
    "assess_nrtl_binary_parameters",
    "extract_model_quality_warnings",
    "history_has_nrtl_zero_binary_warning",
    "normalize_component_pair",
    "nrtl_binary_parameter_sources",
    "provided_nrtl_binary_pairs",
    "required_nrtl_binary_pairs",
]
