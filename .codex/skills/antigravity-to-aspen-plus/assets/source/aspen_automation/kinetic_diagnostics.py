from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .schema import PlantSpecification
from .serialization import spec_to_plain_dict


DEFAULT_PRE_EXPONENTIAL_MULTIPLIERS = (1.0, 1e3, 1e6, 1e9)
DEFAULT_ACTIVATION_ENERGY_OVERRIDES = (None, 0.0)


@dataclass(frozen=True)
class KineticSweepCase:
    label: str
    spec: PlantSpecification
    pre_exponential_multiplier: float
    activation_energy_override: float | None


def build_reactor_only_kinetic_sweep_specs(
    spec: PlantSpecification | Mapping[str, Any],
    *,
    inlet_stream: str = "R-IN",
    outlet_stream: str = "R-OUT",
    reactor_block: str = "B-SYN",
    pre_exponential_multipliers: Sequence[float] = DEFAULT_PRE_EXPONENTIAL_MULTIPLIERS,
    activation_energy_overrides: Sequence[float | None] = DEFAULT_ACTIVATION_ENERGY_OVERRIDES,
) -> list[KineticSweepCase]:
    spec_obj = _ensure_spec(spec)
    source = spec_to_plain_dict(spec_obj)

    inlet = _find_named(source.get("streams", []), inlet_stream, "stream")
    block = _find_named(source.get("blocks", []), reactor_block, "block")
    reaction_set_id = block.get("reactions")
    if not reaction_set_id:
        raise ValueError(f"Reactor block '{reactor_block}' does not reference a reaction set.")

    reaction_sets = [
        reaction_set
        for reaction_set in source.get("reaction_sets") or []
        if reaction_set.get("id") == reaction_set_id
    ]
    if not reaction_sets:
        raise ValueError(f"Reaction set '{reaction_set_id}' referenced by '{reactor_block}' was not found.")

    reaction_ids = set(reaction_sets[0].get("reaction_ids") or [])
    chemistry = _filtered_chemistry(source.get("chemistry") or [], reaction_ids)
    if not chemistry:
        raise ValueError(f"No chemistry reactions found for reaction set '{reaction_set_id}'.")

    cases: list[KineticSweepCase] = []
    for multiplier in pre_exponential_multipliers:
        for activation_override in activation_energy_overrides:
            case_data = dict(source)
            case_data["flowsheet"] = [
                {"block": reactor_block, "inputs": [inlet_stream], "outputs": [outlet_stream]}
            ]
            case_data["streams"] = [
                dict(inlet),
                _build_outlet_guess_from_inlet(inlet, outlet_stream, block),
            ]
            case_data["blocks"] = [dict(block)]
            case_data["reaction_sets"] = [dict(reaction_sets[0])]
            case_data["chemistry"] = _scale_kinetic_chemistry(
                chemistry,
                pre_exponential_multiplier=float(multiplier),
                activation_energy_override=activation_override,
            )
            targets = dict(case_data.get("targets") or {})
            targets.pop("product_conditions", None)
            targets.pop("component_loss_limits", None)
            case_data["targets"] = targets

            case_spec = PlantSpecification(**case_data)
            cases.append(
                KineticSweepCase(
                    label=_case_label(float(multiplier), activation_override),
                    spec=case_spec,
                    pre_exponential_multiplier=float(multiplier),
                    activation_energy_override=activation_override,
                )
            )

    return cases


def diagnose_kinetic_sweep_results(
    case_results: Iterable[Mapping[str, Any] | Any],
    *,
    min_ch3oh_mole_frac_delta: float = 1e-7,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    triggering_case_label: str | None = None

    for index, case_result in enumerate(case_results):
        label = _get_case_value(case_result, "label", f"case_{index}")
        multiplier = _get_case_value(case_result, "pre_exponential_multiplier", None)
        activation_override = _get_case_value(case_result, "activation_energy_override", None)

        inlet_ch3oh = _extract_case_ch3oh(case_result, "inlet_ch3oh_mole_frac", "R-IN")
        outlet_ch3oh = _extract_case_ch3oh(case_result, "outlet_ch3oh_mole_frac", "R-OUT")
        delta = outlet_ch3oh - inlet_ch3oh
        amplified_or_zero_e = (multiplier is not None and float(multiplier) != 1.0) or activation_override is not None
        methanol_appeared = amplified_or_zero_e and delta > min_ch3oh_mole_frac_delta

        row = {
            "label": label,
            "pre_exponential_multiplier": multiplier,
            "activation_energy_override": activation_override,
            "inlet_ch3oh_mole_frac": inlet_ch3oh,
            "outlet_ch3oh_mole_frac": outlet_ch3oh,
            "delta_ch3oh_mole_frac": delta,
            "methanol_appeared": methanol_appeared,
        }
        rows.append(row)

        if methanol_appeared and triggering_case_label is None:
            triggering_case_label = str(label)

    diagnosis = (
        "kinetic_scaling_or_units"
        if triggering_case_label is not None
        else "powerlaw_rplug_specification"
    )
    return {
        "diagnosis": diagnosis,
        "methanol_appeared": triggering_case_label is not None,
        "triggering_case_label": triggering_case_label,
        "min_ch3oh_mole_frac_delta": min_ch3oh_mole_frac_delta,
        "rows": rows,
    }


def _ensure_spec(spec: PlantSpecification | Mapping[str, Any]) -> PlantSpecification:
    if isinstance(spec, PlantSpecification):
        return PlantSpecification(**spec_to_plain_dict(spec))
    if isinstance(spec, Mapping):
        return PlantSpecification(**spec_to_plain_dict(spec))
    raise TypeError(f"spec must be PlantSpecification or mapping; got {type(spec).__name__}")


def _find_named(items: Iterable[Mapping[str, Any]], name: str, item_kind: str) -> dict[str, Any]:
    for item in items:
        if item.get("name") == name:
            return dict(item)
    raise ValueError(f"Required {item_kind} '{name}' was not found.")


def _filtered_chemistry(chemistry_sections: Sequence[Mapping[str, Any]], reaction_ids: set[int]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for section in chemistry_sections:
        reactions = [
            dict(reaction)
            for reaction in section.get("reactions", [])
            if reaction.get("id") in reaction_ids
        ]
        if reactions:
            copied = dict(section)
            copied["reactions"] = reactions
            filtered.append(copied)
    return filtered


def _build_outlet_guess_from_inlet(
    inlet: Mapping[str, Any],
    outlet_stream: str,
    block: Mapping[str, Any],
) -> dict[str, Any]:
    outlet = dict(inlet)
    outlet["name"] = outlet_stream
    parameters = block.get("parameters") or {}
    if "TEMP" in parameters:
        outlet["temperature"] = parameters["TEMP"]
    if "PRES" in parameters:
        outlet["pressure"] = parameters["PRES"]
    return outlet


def _scale_kinetic_chemistry(
    chemistry: Sequence[Mapping[str, Any]],
    *,
    pre_exponential_multiplier: float,
    activation_energy_override: float | None,
) -> list[dict[str, Any]]:
    scaled_sections: list[dict[str, Any]] = []
    for section in chemistry:
        copied_section = dict(section)
        scaled_reactions: list[dict[str, Any]] = []
        for reaction in section.get("reactions", []):
            copied_reaction = dict(reaction)
            parameters = dict(copied_reaction.get("parameters") or {})
            if str(parameters.get("reaction_type", "")).upper() == "KINETIC":
                pre_exp = parameters.get("pre_exponential_factor")
                if pre_exp is not None:
                    parameters["pre_exponential_factor"] = float(pre_exp) * pre_exponential_multiplier
                if activation_energy_override is not None:
                    parameters["activation_energy"] = activation_energy_override
            copied_reaction["parameters"] = parameters
            scaled_reactions.append(copied_reaction)
        copied_section["reactions"] = scaled_reactions
        scaled_sections.append(copied_section)
    return scaled_sections


def _case_label(multiplier: float, activation_energy_override: float | None) -> str:
    multiplier_label = f"{multiplier:g}".replace("+", "")
    energy_label = "original_E" if activation_energy_override is None else f"E_{activation_energy_override:g}"
    return f"preexp_x{multiplier_label}_{energy_label}"


def _get_case_value(case_result: Mapping[str, Any] | Any, key: str, default: Any) -> Any:
    if isinstance(case_result, Mapping):
        return case_result.get(key, default)
    return getattr(case_result, key, default)


def _extract_case_ch3oh(case_result: Mapping[str, Any] | Any, direct_key: str, stream_name: str) -> float:
    direct = _get_case_value(case_result, direct_key, None)
    if direct is not None:
        return float(direct)

    streams = _get_case_value(case_result, "streams", None)
    if streams is None:
        raise ValueError(f"Case result is missing '{direct_key}' or stream table data.")

    value = _extract_stream_component_value(streams, stream_name, "CH3OH_mole_frac")
    if value is None:
        raise ValueError(f"Stream '{stream_name}' is missing CH3OH_mole_frac.")
    return float(value)


def _extract_stream_component_value(streams: Any, stream_name: str, column: str) -> Any:
    if hasattr(streams, "columns") and "stream_name" in streams.columns:
        matches = streams[streams["stream_name"] == stream_name]
        if len(matches) == 0:
            return None
        return matches.iloc[0].get(column)

    if isinstance(streams, Mapping):
        row = streams.get(stream_name)
        if row is None:
            return None
        if isinstance(row, Mapping):
            return row.get(column)
        return getattr(row, column, None)

    if isinstance(streams, Iterable) and not isinstance(streams, (str, bytes, bytearray)):
        for row in streams:
            row_name = row.get("stream_name") if isinstance(row, Mapping) else getattr(row, "stream_name", None)
            if row_name != stream_name:
                continue
            return row.get(column) if isinstance(row, Mapping) else getattr(row, column, None)

    return None


__all__ = [
    "KineticSweepCase",
    "build_reactor_only_kinetic_sweep_specs",
    "diagnose_kinetic_sweep_results",
]
