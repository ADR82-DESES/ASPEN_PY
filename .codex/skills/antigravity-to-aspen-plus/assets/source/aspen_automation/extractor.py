from __future__ import annotations

import datetime
import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import pandas as pd

from .exceptions import ExtractionError
from .serialization import spec_to_plain_dict
from .schema import PlantSpecification
from .simulation_diagnostics import read_aspen_run_diagnostics

logger = logging.getLogger("aspen_automation.extractor")

ENERGY_BALANCE_VIEW_LEGACY = "legacy"
ENERGY_BALANCE_VIEW_SUMMARY = "summary"
METHANOL_COMPONENT_ID = "CH3OH"


def _spec_to_dict(spec: Union[PlantSpecification, Dict[str, Any]]) -> Dict[str, Any]:
    return spec_to_plain_dict(spec)


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(converted):
        return None
    return converted


def _get_node_value(aspen: Any, path: str) -> Optional[float]:
    try:
        node = aspen.Tree.FindNode(path)
        if node is None:
            return None
        return _as_float(node.Value)
    except Exception:
        return None


def _safe_node_value(aspen: Any, path: str) -> Optional[float]:
    return _get_node_value(aspen, path)


def _get_text_node_value(aspen: Any, path: str) -> Optional[str]:
    try:
        node = aspen.Tree.FindNode(path)
        if node is None:
            return None
        value = node.Value
    except Exception:
        return None
    if value is None:
        return None
    return str(value)


def _get_element_names(aspen: Any, node_path: str) -> List[str]:
    names: List[str] = []
    try:
        node = aspen.Tree.FindNode(node_path)
        if node is None:
            return names
        count = int(node.Elements.Count)
    except Exception:
        return names

    for index in range(1, count + 1):
        try:
            element = node.Elements.Item(index)
            element_name = getattr(element, "Name", None)
            if element_name:
                names.append(str(element_name))
        except Exception:
            continue
    return names


def _component_ids(spec_dict: Dict[str, Any]) -> List[str]:
    component_ids: List[str] = []
    for component in spec_dict.get("components", []):
        if isinstance(component, dict) and component.get("id"):
            component_ids.append(str(component["id"]))
    return component_ids


def _stream_names(spec_dict: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    for stream in spec_dict.get("streams", []):
        if isinstance(stream, dict) and stream.get("name"):
            names.append(str(stream["name"]))
    return names


def _block_specs(spec_dict: Dict[str, Any]) -> List[Tuple[str, Optional[str]]]:
    specs: List[Tuple[str, Optional[str]]] = []
    for block in spec_dict.get("blocks", []):
        if not isinstance(block, dict):
            continue
        name = block.get("name")
        if not name:
            continue
        block_type = block.get("type")
        specs.append((str(name), str(block_type) if block_type is not None else None))
    return specs


def _streams_columns(component_ids: Sequence[str]) -> List[str]:
    columns = ["stream_name", "temperature", "pressure", "mass_flow", "mole_flow"]
    for component_id in component_ids:
        columns.append(f"{component_id}_mole_frac")
        columns.append(f"{component_id}_mass_frac")
    return columns


def _extract_stream_row(aspen: Any, stream_name: str, components: Sequence[str]) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "stream_name": stream_name,
        "temperature": _get_node_value(aspen, rf"\Data\Streams\{stream_name}\Output\TEMP_OUT\MIXED"),
        "pressure": _get_node_value(aspen, rf"\Data\Streams\{stream_name}\Output\PRES_OUT\MIXED"),
        "mass_flow": _get_node_value(aspen, rf"\Data\Streams\{stream_name}\Output\MASSFLMX\MIXED"),
        "mole_flow": _get_node_value(aspen, rf"\Data\Streams\{stream_name}\Output\MOLEFLMX\MIXED"),
    }

    for component in components:
        row[f"{component}_mole_frac"] = _get_node_value(
            aspen, rf"\Data\Streams\{stream_name}\Output\MOLEFRAC\MIXED\{component}"
        )
        row[f"{component}_mass_frac"] = _get_node_value(
            aspen, rf"\Data\Streams\{stream_name}\Output\MASSFRAC\MIXED\{component}"
        )
    return row


def extract_stream_properties(aspen: Any, stream_names: List[str], component_ids: List[str]) -> pd.DataFrame:
    rows = [_extract_stream_row(aspen, stream_name, component_ids) for stream_name in stream_names]
    return pd.DataFrame(rows, columns=_streams_columns(component_ids))


def _extract_block_row(aspen: Any, block_name: str, block_type: Optional[str] = None) -> Dict[str, Any]:
    detected_type = block_type or _get_text_node_value(aspen, rf"\Data\Blocks\{block_name}\Input\TYPE")
    duty_kw = _get_node_value(aspen, rf"\Data\Blocks\{block_name}\Output\QNET")
    if duty_kw is None:
        duty_kw = _get_node_value(aspen, rf"\Data\Blocks\{block_name}\Output\DUTY")

    net_work_kw = _get_node_value(aspen, rf"\Data\Blocks\{block_name}\Output\WNET")
    conversion = _get_node_value(aspen, rf"\Data\Blocks\{block_name}\Output\CONV")
    efficiency = _get_node_value(aspen, rf"\Data\Blocks\{block_name}\Output\EFF")

    return {
        "block_name": block_name,
        "block_type": detected_type,
        "duty": duty_kw,
        "duty_kw": duty_kw,
        "duty_mw": (duty_kw / 1000.0) if duty_kw is not None else None,
        "net_work_kw": net_work_kw,
        "conversion": conversion,
        "efficiency": efficiency,
    }


def extract_block_performance(aspen: Any, block_names: List[str]) -> pd.DataFrame:
    rows = [_extract_block_row(aspen, block_name) for block_name in block_names]
    columns = [
        "block_name",
        "block_type",
        "duty",
        "duty_kw",
        "duty_mw",
        "net_work_kw",
        "conversion",
        "efficiency",
    ]
    return pd.DataFrame(rows, columns=columns)


def _identify_feed_product_streams(
    spec: Union[PlantSpecification, Dict[str, Any]]
) -> Tuple[List[str], List[str]]:
    spec_dict = _spec_to_dict(spec)
    all_inputs: set[str] = set()
    all_outputs: set[str] = set()

    for connection in spec_dict.get("flowsheet", []):
        if not isinstance(connection, dict):
            continue
        inputs = connection.get("inputs", [])
        outputs = connection.get("outputs", [])
        if isinstance(inputs, list):
            for stream_name in inputs:
                if stream_name:
                    all_inputs.add(str(stream_name))
        if isinstance(outputs, list):
            for stream_name in outputs:
                if stream_name:
                    all_outputs.add(str(stream_name))

    feed_streams = sorted(all_inputs - all_outputs)
    product_streams = sorted(all_outputs - all_inputs)
    return feed_streams, product_streams


_PURITY_RE = re.compile(
    r"^\s*(?P<component>\S+)\s+"
    r"(?P<basis>wt%|mass%|weight%|mol%|mole%|mass\s+fraction|mole\s+fraction)\s+"
    r"in\s+(?P<stream>\S+)\s*$",
    flags=re.IGNORECASE,
)


def _parse_purity_expression(expression: str) -> Tuple[str, str, str]:
    match = _PURITY_RE.match(expression or "")
    if not match:
        raise ValueError(
            "Purity expression must follow '<component> <wt%|mol%|mass fraction|mole fraction> in <stream>'."
        )
    component = match.group("component").strip()
    basis_raw = match.group("basis").strip().lower()
    stream_name = match.group("stream").strip()

    if basis_raw in {"wt%", "mass%", "weight%", "mass fraction"}:
        basis = "mass"
    else:
        basis = "mole"
    return component, basis, stream_name


def parse_purity_expression(expression: str) -> Tuple[str, str, str]:
    component, basis, stream_name = _parse_purity_expression(expression)
    basis_token = "wt%" if basis == "mass" else "mol%"
    return component, basis_token, stream_name


def _resolve_column_case_insensitive(df: pd.DataFrame, expected: str) -> Optional[str]:
    expected_lower = expected.lower()
    for column in df.columns:
        if str(column).lower() == expected_lower:
            return str(column)
    return None


def _numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(df[column], errors="coerce")


def _evaluate_purity(streams_df: pd.DataFrame, expression: str) -> Optional[float]:
    if streams_df.empty:
        return None

    try:
        component, basis, stream_name = _parse_purity_expression(expression)
    except ValueError:
        logger.warning("Invalid purity expression '%s'; returning None.", expression)
        return None
    stream_column = _resolve_column_case_insensitive(streams_df, "stream_name")
    if stream_column is None:
        return None

    stream_mask = streams_df[stream_column].astype(str).str.upper() == stream_name.upper()
    if not stream_mask.any():
        return None

    candidate_column = f"{component}_{'mass_frac' if basis == 'mass' else 'mole_frac'}"
    purity_column = _resolve_column_case_insensitive(streams_df, candidate_column)
    if purity_column is None:
        return None

    value = streams_df.loc[stream_mask, purity_column].iloc[0]
    return _as_float(value)


def evaluate_purity(aspen_or_streams: Any, expression: str) -> Optional[float]:
    if isinstance(aspen_or_streams, pd.DataFrame):
        return _evaluate_purity(aspen_or_streams, expression)

    component, basis, stream_name = _parse_purity_expression(expression)
    if basis == "mass":
        path = rf"\Data\Streams\{stream_name}\Output\MASSFRAC\MIXED\{component}"
    else:
        path = rf"\Data\Streams\{stream_name}\Output\MOLEFRAC\MIXED\{component}"
    return _get_node_value(aspen_or_streams, path)


def _sum_component_flow(aspen: Any, stream_names: Iterable[str], component_id: str) -> float:
    total = 0.0
    for stream_name in stream_names:
        mole_flow = _get_node_value(aspen, rf"\Data\Streams\{stream_name}\Output\MOLEFLMX\MIXED")
        mole_fraction = _get_node_value(
            aspen, rf"\Data\Streams\{stream_name}\Output\MOLEFRAC\MIXED\{component_id}"
        )
        if mole_flow is None or mole_fraction is None:
            continue
        total += mole_flow * mole_fraction
    return total


def calculate_material_balance(
    aspen: Any, spec: Union[PlantSpecification, Dict[str, Any]]
) -> pd.DataFrame:
    spec_dict = _spec_to_dict(spec)
    component_ids = _component_ids(spec_dict)
    feed_streams, product_streams = _identify_feed_product_streams(spec_dict)

    rows: List[Dict[str, Any]] = []
    for component_id in component_ids:
        input_kmol_hr = _sum_component_flow(aspen, feed_streams, component_id)
        output_kmol_hr = _sum_component_flow(aspen, product_streams, component_id)
        closure_pct = None
        if input_kmol_hr > 0:
            closure_pct = (output_kmol_hr / input_kmol_hr - 1.0) * 100.0

        rows.append(
            {
                "component_id": component_id,
                "component": component_id,
                "input_kmol_hr": input_kmol_hr,
                "output_kmol_hr": output_kmol_hr,
                "closure_pct": closure_pct,
                "closure_%": closure_pct,
            }
        )

    columns = ["component_id", "component", "input_kmol_hr", "output_kmol_hr", "closure_pct", "closure_%"]
    return pd.DataFrame(rows, columns=columns)


def calculate_energy_balance(
    aspen: Any,
    spec: Union[PlantSpecification, Dict[str, Any]],
    energy_balance_view: str = ENERGY_BALANCE_VIEW_LEGACY,
) -> pd.DataFrame:
    spec_dict = _spec_to_dict(spec)
    block_specs = _block_specs(spec_dict)

    if not block_specs:
        block_specs = [(name, None) for name in _get_element_names(aspen, r"\Data\Blocks")]

    block_rows = [_extract_block_row(aspen, name, block_type) for name, block_type in block_specs]
    blocks_df = pd.DataFrame(
        block_rows,
        columns=["block_name", "block_type", "duty", "duty_kw", "duty_mw", "net_work_kw", "conversion", "efficiency"],
    )
    return _energy_balance_from_blocks(blocks_df, energy_balance_view=energy_balance_view)


def _normalize_energy_balance_view(energy_balance_view: Optional[str]) -> str:
    if energy_balance_view is None:
        return ENERGY_BALANCE_VIEW_LEGACY

    normalized_view = str(energy_balance_view).strip().lower()
    if normalized_view in {"legacy", "per-block", "per_block", "by_block", "blocks"}:
        return ENERGY_BALANCE_VIEW_LEGACY
    if normalized_view in {"summary", "aggregate", "aggregated", "category", "categories"}:
        return ENERGY_BALANCE_VIEW_SUMMARY

    raise ValueError(
        "energy_balance_view must be one of: "
        "'legacy' (aliases: 'per-block', 'per_block', 'by_block', 'blocks') or "
        "'summary' (aliases: 'aggregate', 'aggregated', 'category', 'categories')."
    )


def _energy_balance_from_blocks(
    blocks_df: pd.DataFrame, energy_balance_view: str = ENERGY_BALANCE_VIEW_LEGACY
) -> pd.DataFrame:
    normalized_view = _normalize_energy_balance_view(energy_balance_view)
    if normalized_view == ENERGY_BALANCE_VIEW_SUMMARY:
        return _energy_balance_summary_from_blocks(blocks_df)
    return _energy_balance_legacy_from_blocks(blocks_df)


def _energy_balance_legacy_from_blocks(blocks_df: pd.DataFrame) -> pd.DataFrame:
    columns = ["block_name", "duty", "duty_kw", "duty_mw"]
    if blocks_df.empty:
        return pd.DataFrame(
            [{"block_name": "TOTAL", "duty": 0.0, "duty_kw": 0.0, "duty_mw": 0.0}],
            columns=columns,
        )

    legacy_df = blocks_df.reindex(columns=columns).copy()
    duty_kw = _numeric_series(legacy_df, "duty_kw").dropna()
    total_duty_kw = float(duty_kw.sum()) if not duty_kw.empty else 0.0

    total_row = {
        "block_name": "TOTAL",
        "duty": total_duty_kw,
        "duty_kw": total_duty_kw,
        "duty_mw": total_duty_kw / 1000.0,
    }
    return pd.concat([legacy_df, pd.DataFrame([total_row], columns=columns)], ignore_index=True)


def _energy_balance_summary_from_blocks(blocks_df: pd.DataFrame) -> pd.DataFrame:
    if blocks_df.empty:
        return pd.DataFrame(
            [
                {"category": "Heat Input", "value_mw": 0.0},
                {"category": "Heat Output", "value_mw": 0.0},
                {"category": "Net Work", "value_mw": 0.0},
            ]
        )

    duty_kw = _numeric_series(blocks_df, "duty_kw").dropna()
    work_kw = _numeric_series(blocks_df, "net_work_kw").dropna()

    heat_input_kw = duty_kw[duty_kw > 0].sum()
    heat_output_kw = duty_kw[duty_kw < 0].sum()
    net_work_kw = work_kw.sum()

    return pd.DataFrame(
        [
            {"category": "Heat Input", "value_mw": heat_input_kw / 1000.0},
            {"category": "Heat Output", "value_mw": heat_output_kw / 1000.0},
            {"category": "Net Work", "value_mw": net_work_kw / 1000.0},
        ]
    )


def extract_diagnostics(aspen: Any, spec_dict: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    block_names: Optional[List[str]] = None
    if spec_dict is not None:
        process_defaults = spec_dict.get("process_defaults") or {}
        if isinstance(process_defaults, dict):
            cb = process_defaults.get("convergence_block")
            if cb:
                block_names = [str(cb)]
    return read_aspen_run_diagnostics(aspen, block_names=block_names)


def _pick_product_stream(
    streams_df: pd.DataFrame,
    product_stream_names: Optional[List[str]] = None,
) -> Optional[pd.Series]:
    if streams_df.empty:
        return None

    stream_name_col = _resolve_column_case_insensitive(streams_df, "stream_name")
    if stream_name_col is None:
        return None

    candidate_df = streams_df
    if product_stream_names:
        names_upper = {str(n).upper() for n in product_stream_names}
        mask = streams_df[stream_name_col].astype(str).str.upper().isin(names_upper)
        if mask.any():
            candidate_df = streams_df.loc[mask]

    mass_flow_col = _resolve_column_case_insensitive(candidate_df, "mass_flow")
    if mass_flow_col is not None:
        mass_flow_values = pd.to_numeric(candidate_df[mass_flow_col], errors="coerce")
        if mass_flow_values.notna().any():
            best_index = mass_flow_values.idxmax()
            return candidate_df.loc[best_index]
    return None


def _target_purity_expression(spec_dict: Dict[str, Any]) -> Optional[str]:
    targets = spec_dict.get("targets")
    if isinstance(targets, dict):
        purity = targets.get("purity")
        if isinstance(purity, dict):
            expression = purity.get("expression")
            if expression:
                return str(expression)

    process_defaults = spec_dict.get("process_defaults") or {}
    if isinstance(process_defaults, dict):
        fallback = process_defaults.get("purity_expression")
        if fallback:
            return str(fallback)
    return None


def _target_yield_config(spec_dict: Dict[str, Any]) -> Dict[str, Any]:
    targets = spec_dict.get("targets")
    if not isinstance(targets, dict):
        return {}
    yield_target = targets.get("yield")
    if isinstance(yield_target, dict):
        return yield_target
    return {}


def _optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _stream_names_list(value: Any) -> List[str]:
    if isinstance(value, str):
        stream_name = _optional_text(value)
        return [stream_name] if stream_name else []
    if isinstance(value, (list, tuple, set)):
        names: List[str] = []
        for stream_name in value:
            cleaned = _optional_text(stream_name)
            if cleaned:
                names.append(cleaned)
        return names
    return []


def _stream_row_by_name(streams_df: pd.DataFrame, stream_name: str) -> Optional[pd.Series]:
    stream_name_col = _resolve_column_case_insensitive(streams_df, "stream_name")
    if stream_name_col is None:
        return None
    stream_mask = streams_df[stream_name_col].astype(str).str.upper() == stream_name.upper()
    if not stream_mask.any():
        return None
    return streams_df.loc[stream_mask].iloc[0]


def _component_mole_flow_from_row(
    streams_df: pd.DataFrame, row: Optional[pd.Series], component_id: Optional[str]
) -> Optional[float]:
    if row is None or not component_id:
        return None

    mole_flow_col = _resolve_column_case_insensitive(streams_df, "mole_flow")
    component_mole_frac_col = _resolve_column_case_insensitive(streams_df, f"{component_id}_mole_frac")
    if mole_flow_col is None or component_mole_frac_col is None:
        return None

    mole_flow = _as_float(row.get(mole_flow_col))
    mole_fraction = _as_float(row.get(component_mole_frac_col))
    if mole_flow is None or mole_fraction is None:
        return None
    return mole_flow * mole_fraction


def _component_mass_flow_from_row(
    streams_df: pd.DataFrame, row: Optional[pd.Series], component_id: Optional[str]
) -> Optional[float]:
    if row is None or not component_id:
        return None

    mass_flow_col = _resolve_column_case_insensitive(streams_df, "mass_flow")
    component_mass_frac_col = _resolve_column_case_insensitive(streams_df, f"{component_id}_mass_frac")
    if mass_flow_col is None or component_mass_frac_col is None:
        return None

    mass_flow = _as_float(row.get(mass_flow_col))
    mass_fraction = _as_float(row.get(component_mass_frac_col))
    if mass_flow is None or mass_fraction is None:
        return None
    return mass_flow * mass_fraction


def _mole_component_flow(
    streams_df: pd.DataFrame, stream_name: str, component_id: str
) -> Optional[float]:
    row = _stream_row_by_name(streams_df, stream_name)
    return _component_mole_flow_from_row(streams_df, row, component_id)


def _conversion_fraction(inlet_flow: Optional[float], outlet_flow: Optional[float]) -> Optional[float]:
    if inlet_flow is None or outlet_flow is None or inlet_flow <= 0:
        return None
    return (inlet_flow - outlet_flow) / inlet_flow


def _delta_flow(inlet_flow: Optional[float], outlet_flow: Optional[float]) -> Optional[float]:
    if inlet_flow is None or outlet_flow is None:
        return None
    return outlet_flow - inlet_flow


def _stoichiometric_number_from_stream(streams_df: pd.DataFrame, stream_name: str) -> Optional[float]:
    h2 = _mole_component_flow(streams_df, stream_name, "H2")
    co = _mole_component_flow(streams_df, stream_name, "CO")
    co2 = _mole_component_flow(streams_df, stream_name, "CO2")
    if h2 is None or co is None or co2 is None:
        return None
    denominator = co + co2
    if denominator <= 0:
        return None
    return (h2 - co2) / denominator


def _stream_component_fraction(
    streams_df: pd.DataFrame, stream_name: str, component_id: str, basis: str = "mole"
) -> Optional[float]:
    row = _stream_row_by_name(streams_df, stream_name)
    if row is None:
        return None
    column = _resolve_column_case_insensitive(streams_df, f"{component_id}_{basis}_frac")
    if column is None:
        return None
    return _as_float(row.get(column))


def _find_block_connection(spec_dict: Dict[str, Any], block_name: str) -> tuple[Optional[str], Optional[str]]:
    for connection in spec_dict.get("flowsheet", []):
        if not isinstance(connection, dict):
            continue
        if str(connection.get("block", "")).upper() != block_name.upper():
            continue
        inputs = connection.get("inputs", [])
        outputs = connection.get("outputs", [])
        inlet = str(inputs[0]) if isinstance(inputs, list) and inputs else None
        outlet = str(outputs[0]) if isinstance(outputs, list) and outputs else None
        return inlet, outlet
    return None, None


def calculate_synthesis_loop_diagnostics(
    spec: Union[PlantSpecification, Dict[str, Any]],
    streams_df: pd.DataFrame,
    *,
    block_name: str = "B-SYN",
) -> Dict[str, Any]:
    spec_dict = _spec_to_dict(spec)
    inlet_stream, outlet_stream = _find_block_connection(spec_dict, block_name)
    if streams_df.empty or inlet_stream is None or outlet_stream is None:
        return {
            "block": block_name,
            "available": False,
            "reason": "Missing synthesis block connection or stream results.",
        }

    inlet_flows = {
        component: _mole_component_flow(streams_df, inlet_stream, component)
        for component in ("CO", "CO2", "H2", "CH3OH", "CH4")
    }
    outlet_flows = {
        component: _mole_component_flow(streams_df, outlet_stream, component)
        for component in ("CO", "CO2", "H2", "CH3OH", "CH4")
    }

    return {
        "block": block_name,
        "available": True,
        "inlet_stream": inlet_stream,
        "outlet_stream": outlet_stream,
        "co_conversion_fraction": _conversion_fraction(inlet_flows["CO"], outlet_flows["CO"]),
        "co2_conversion_fraction": _conversion_fraction(inlet_flows["CO2"], outlet_flows["CO2"]),
        "h2_consumption_fraction": _conversion_fraction(inlet_flows["H2"], outlet_flows["H2"]),
        "methanol_formation_kmol_hr": _delta_flow(inlet_flows["CH3OH"], outlet_flows["CH3OH"]),
        "methane_change_kmol_hr": _delta_flow(inlet_flows["CH4"], outlet_flows["CH4"]),
        "inlet_stoichiometric_number": _stoichiometric_number_from_stream(streams_df, inlet_stream),
        "inlet_ch4_mole_frac": _stream_component_fraction(streams_df, inlet_stream, "CH4"),
        "inlet_co2_mole_frac": _stream_component_fraction(streams_df, inlet_stream, "CO2"),
        "outlet_ch3oh_mole_frac": _stream_component_fraction(streams_df, outlet_stream, METHANOL_COMPONENT_ID),
    }


def _feed_component_mole_flow(
    streams_df: pd.DataFrame,
    feed_streams: Sequence[str],
    component_id: Optional[str],
    aggregation: str = "sum",
) -> Optional[float]:
    if streams_df.empty or not feed_streams or not component_id:
        return None

    stream_name_col = _resolve_column_case_insensitive(streams_df, "stream_name")
    if stream_name_col is None:
        return None

    feed_names_upper = {str(name).upper() for name in feed_streams if str(name).strip()}
    if not feed_names_upper:
        return None

    stream_names_upper = streams_df[stream_name_col].astype(str).str.upper()
    feed_rows = streams_df.loc[stream_names_upper.isin(feed_names_upper)]
    if feed_rows.empty:
        return None

    available_feed_names = set(feed_rows[stream_name_col].astype(str).str.upper())
    if not feed_names_upper.issubset(available_feed_names):
        return None

    component_flows: List[float] = []
    for _, feed_row in feed_rows.iterrows():
        component_flow = _component_mole_flow_from_row(streams_df, feed_row, component_id)
        if component_flow is None:
            return None
        component_flows.append(component_flow)

    if not component_flows:
        return None
    if aggregation == "max":
        return max(component_flows)
    return float(sum(component_flows))


def calculate_kpis(
    aspen: Any,
    spec: Union[PlantSpecification, Dict[str, Any]],
    streams_df: pd.DataFrame,
    blocks_df: pd.DataFrame,
) -> Dict[str, Any]:
    spec_dict = _spec_to_dict(spec)
    diagnostics = extract_diagnostics(aspen, spec_dict=spec_dict)

    production_rate_tpd: Optional[float] = None
    product_stream_name: Optional[str] = None
    product_total_tpd: Optional[float] = None
    yield_fraction: Optional[float] = None
    process_defaults = spec_dict.get("process_defaults") or {}
    explicit_product = (
        process_defaults.get("product_stream")
        if isinstance(process_defaults, dict)
        else None
    )
    if explicit_product:
        product_row = _pick_product_stream(streams_df, product_stream_names=[str(explicit_product)])
    else:
        _, spec_product_streams = _identify_feed_product_streams(spec_dict)
        product_row = _pick_product_stream(streams_df, product_stream_names=spec_product_streams)

    if product_row is not None:
        stream_name_col = _resolve_column_case_insensitive(streams_df, "stream_name")
        if stream_name_col is not None:
            product_stream_value = product_row.get(stream_name_col)
            if product_stream_value is not None:
                product_stream_name = str(product_stream_value)
        mass_flow = _as_float(product_row.get("mass_flow"))
        if mass_flow is not None:
            production_rate_tpd = mass_flow * 24.0 / 1000.0
            product_total_tpd = production_rate_tpd

    purity_expression = _target_purity_expression(spec_dict)
    purity_fraction = _evaluate_purity(streams_df, purity_expression) if purity_expression else None

    default_yield_component: Optional[str] = None
    if purity_expression:
        try:
            default_yield_component, _, _ = _parse_purity_expression(purity_expression)
        except ValueError:
            default_yield_component = None

    yield_target = _target_yield_config(spec_dict)
    yield_component = _optional_text(yield_target.get("component")) or default_yield_component

    yield_product_stream = _optional_text(yield_target.get("stream")) or _optional_text(
        yield_target.get("product_stream")
    )
    yield_product_row = (
        _stream_row_by_name(streams_df, yield_product_stream) if yield_product_stream else product_row
    )

    selected_feed_streams, _ = _identify_feed_product_streams(spec_dict)
    feed_streams_override = _stream_names_list(yield_target.get("feed_streams"))
    if not feed_streams_override:
        feed_streams_override = _stream_names_list(yield_target.get("feed_stream"))
    if feed_streams_override:
        selected_feed_streams = feed_streams_override

    feed_aggregation = (
        _optional_text(yield_target.get("feed_aggregation")) or _optional_text(yield_target.get("feed_basis")) or "sum"
    ).lower()
    if feed_aggregation not in {"sum", "max"}:
        feed_aggregation = "sum"

    product_component_mole_flow = _component_mole_flow_from_row(streams_df, yield_product_row, yield_component)
    feed_component_mole_flow = _feed_component_mole_flow(
        streams_df, selected_feed_streams, yield_component, aggregation=feed_aggregation
    )
    if (
        product_component_mole_flow is not None
        and feed_component_mole_flow is not None
        and feed_component_mole_flow > 0
    ):
        yield_fraction = product_component_mole_flow / feed_component_mole_flow

    product_component_mass_flow = _component_mass_flow_from_row(streams_df, product_row, yield_component)
    product_component_tpd = (
        product_component_mass_flow * 24.0 / 1000.0 if product_component_mass_flow is not None else None
    )
    methanol_mass_flow = _component_mass_flow_from_row(streams_df, product_row, METHANOL_COMPONENT_ID)
    methanol_tpd = methanol_mass_flow * 24.0 / 1000.0 if methanol_mass_flow is not None else None

    duty_kw = _numeric_series(blocks_df, "duty_kw").dropna()
    energy_consumption_mw = float(duty_kw.abs().sum() / 1000.0) if not duty_kw.empty else 0.0
    synthesis_loop = calculate_synthesis_loop_diagnostics(spec_dict, streams_df)

    return {
        "production_rate_tpd": production_rate_tpd,
        "product_stream": product_stream_name,
        "product_total_tpd": product_total_tpd,
        "product_component": yield_component,
        "product_component_tpd": product_component_tpd,
        "methanol_tpd": methanol_tpd,
        "purity_fraction": purity_fraction,
        "energy_consumption_mw": energy_consumption_mw,
        "yield_fraction": yield_fraction,
        "convergence_status": diagnostics.get("convergence_status", "unknown"),
        "synthesis_loop": synthesis_loop,
    }


def extract_results(
    aspen: Any,
    spec: Union[PlantSpecification, Dict[str, Any]],
    energy_balance_view: str = ENERGY_BALANCE_VIEW_LEGACY,
) -> Dict[str, Any]:
    try:
        spec_dict = _spec_to_dict(spec)
    except Exception as exc:
        raise ExtractionError(str(exc)) from exc

    try:
        component_ids = _component_ids(spec_dict)
        stream_names = _stream_names(spec_dict) or _get_element_names(aspen, r"\Data\Streams")
        block_specs = _block_specs(spec_dict)
        if not block_specs:
            block_specs = [(name, None) for name in _get_element_names(aspen, r"\Data\Blocks")]

        stream_rows = [_extract_stream_row(aspen, stream_name, component_ids) for stream_name in stream_names]
        streams_df = pd.DataFrame(stream_rows, columns=_streams_columns(component_ids))

        block_rows = [_extract_block_row(aspen, name, block_type) for name, block_type in block_specs]
        blocks_df = pd.DataFrame(
            block_rows,
            columns=["block_name", "block_type", "duty", "duty_kw", "duty_mw", "net_work_kw", "conversion", "efficiency"],
        )

        material_balance = calculate_material_balance(aspen, spec_dict)
        energy_balance = _energy_balance_from_blocks(blocks_df, energy_balance_view=energy_balance_view)
        diagnostics = extract_diagnostics(aspen, spec_dict=spec_dict)
        kpis = calculate_kpis(aspen, spec_dict, streams_df, blocks_df)

        metadata = {
            "extracted_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "stream_count": int(len(streams_df)),
            "block_count": int(len(blocks_df)),
            "component_count": int(len(component_ids)),
        }

        return {
            "streams": streams_df,
            "blocks": blocks_df,
            "material_balance": material_balance,
            "energy_balance": energy_balance,
            "kpis": kpis,
            "diagnostics": diagnostics,
            "metadata": metadata,
        }
    except Exception as exc:
        raise ExtractionError(f"Failed to extract simulation results: {exc}") from exc
