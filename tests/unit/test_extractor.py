from __future__ import annotations

import sys
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pandas as pd
import pytest

# Keep package imports stable on non-Windows CI.
sys.modules["win32com"] = MagicMock()
sys.modules["win32com.client"] = MagicMock()

from aspen_automation.extractor import (
    CAL_PER_SEC_TO_KW,
    CAL_PER_SEC_TO_MW,
    _identify_feed_product_streams,
    extract_results,
)


def _node(value: Any) -> MagicMock:
    node = MagicMock()
    node.Value = value
    return node


def _collection_node(names: list[str]) -> MagicMock:
    node = MagicMock()
    elements = MagicMock()
    elements.Count = len(names)

    def _item(index: Any) -> Optional[MagicMock]:
        if isinstance(index, int):
            if 1 <= index <= len(names):
                item = MagicMock()
                item.Name = names[index - 1]
                return item
            return None
        for name in names:
            if str(index).upper() == name.upper():
                item = MagicMock()
                item.Name = name
                return item
        return None

    elements.Item.side_effect = _item
    node.Elements = elements
    return node


def mock_aspen_factory(
    stream_values: Dict[str, Dict[str, Any]],
    block_values: Dict[str, Dict[str, Any]],
    diagnostics: Optional[Dict[str, Any]] = None,
) -> MagicMock:
    diagnostics = diagnostics or {"PER_ERROR": 0, "NERROR": 0, "NWARN": 0}
    aspen = MagicMock()

    def _find_node(path: str) -> Optional[MagicMock]:
        if path == r"\Data\Streams":
            return _collection_node(list(stream_values.keys()))
        if path == r"\Data\Blocks":
            return _collection_node(list(block_values.keys()))

        if path == r"\Data\Results Summary\Run-Status\Output\PER_ERROR":
            return _node(diagnostics.get("PER_ERROR"))
        if path == r"\Data\Convergence\Batch-Options\Output\PER_ERROR":
            value = diagnostics.get("ALT_PER_ERROR")
            return _node(value) if value is not None else None
        if path == r"\Data\Convergence\Sequence\Batch-Options\Output\PER_ERROR":
            value = diagnostics.get("ALT_SEQUENCE_PER_ERROR")
            return _node(value) if value is not None else None
        if path == r"\Data\Results Summary\Convergence\Output\PER_ERROR":
            value = diagnostics.get("ALT_SUMMARY_PER_ERROR")
            return _node(value) if value is not None else None
        if path == r"\Data\Results Summary\Run-Status\Output\NERROR":
            return _node(diagnostics.get("NERROR"))
        if path == r"\Data\Results Summary\Convergence\Output\NERROR":
            value = diagnostics.get("ALT_NERROR")
            return _node(value) if value is not None else None
        if path == r"\Data\Results Summary\Run-Status\Output\NWARN":
            return _node(diagnostics.get("NWARN"))
        if path == r"\Data\Results Summary\Convergence\Output\NWARN":
            value = diagnostics.get("ALT_NWARN")
            return _node(value) if value is not None else None
        if path == r"\Data\Results Summary\Run-Status\Output\MESSAGES":
            value = diagnostics.get("MESSAGES")
            return _node(value) if value is not None else None
        if path == r"\Data\Results Summary\Convergence\Output\MESSAGES":
            value = diagnostics.get("ALT_MESSAGES")
            return _node(value) if value is not None else None

        stream_prefix = "\\Data\\Streams\\"
        if path.startswith(stream_prefix):
            rest = path[len(stream_prefix) :]
            parts = rest.split("\\")
            if len(parts) >= 4 and parts[1] == "Output":
                stream_name = parts[0]
                prop = parts[2]
                basis_or_phase = parts[3]
                if basis_or_phase != "MIXED":
                    return None
                stream_data = stream_values.get(stream_name, {})
                if prop in {"TEMP_OUT", "PRES_OUT", "MASSFLMX", "MOLEFLMX"}:
                    value = stream_data.get(prop)
                    return _node(value) if value is not None else None
                if prop in {"MOLEFRAC", "MASSFRAC"} and len(parts) >= 5:
                    composition = stream_data.get(prop, {})
                    value = composition.get(parts[4]) if isinstance(composition, dict) else None
                    return _node(value) if value is not None else None
            return None

        block_prefix = "\\Data\\Blocks\\"
        if path.startswith(block_prefix):
            rest = path[len(block_prefix) :]
            parts = rest.split("\\")
            if len(parts) >= 3:
                block_name = parts[0]
                scope = parts[1]
                key = parts[2]
                block_data = block_values.get(block_name, {})
                if scope == "Input" and key == "TYPE":
                    value = block_data.get("TYPE")
                    return _node(value) if value is not None else None
                if scope == "Output":
                    value = block_data.get(key)
                    return _node(value) if value is not None else None
            return None

        return None

    aspen.Tree.FindNode.side_effect = _find_node
    return aspen


def _base_spec(with_purity: bool = True, purity_expression: str = "CH3OH wt% in MEOH-PRO") -> Dict[str, Any]:
    spec: Dict[str, Any] = {
        "components": [
            {"id": "CH3OH", "name": "METHANOL"},
            {"id": "H2O", "name": "WATER"},
        ],
        "streams": [
            {"name": "FEED-A"},
            {"name": "INT-1"},
            {"name": "MEOH-PRO"},
        ],
        "blocks": [
            {"name": "R1", "type": "RGIBBS"},
            {"name": "HX1", "type": "HEATER"},
        ],
        "flowsheet": [
            {"block": "R1", "inputs": ["FEED-A"], "outputs": ["INT-1"]},
            {"block": "HX1", "inputs": ["INT-1"], "outputs": ["MEOH-PRO"]},
        ],
    }
    if with_purity:
        spec["targets"] = {"purity": {"expression": purity_expression}}
    return spec


def _base_stream_values() -> Dict[str, Dict[str, Any]]:
    return {
        "FEED-A": {
            "TEMP_OUT": 40.0,
            "PRES_OUT": 30.0,
            "MASSFLMX": 50000.0,
            "MOLEFLMX": 100.0,
            "MOLEFRAC": {"CH3OH": 0.4, "H2O": 0.6},
            "MASSFRAC": {"CH3OH": 0.35, "H2O": 0.65},
        },
        "INT-1": {
            "TEMP_OUT": 210.0,
            "PRES_OUT": 28.0,
            "MASSFLMX": 65000.0,
            "MOLEFLMX": 90.0,
            "MOLEFRAC": {"CH3OH": 0.5, "H2O": 0.5},
            "MASSFRAC": {"CH3OH": 0.6, "H2O": 0.4},
        },
        "MEOH-PRO": {
            "TEMP_OUT": 35.0,
            "PRES_OUT": 25.0,
            "MASSFLMX": 100000.0,
            "MOLEFLMX": 80.0,
            "MOLEFRAC": {"CH3OH": 0.95, "H2O": 0.05},
            "MASSFRAC": {"CH3OH": 0.99, "H2O": 0.01},
        },
    }


def _base_block_values() -> Dict[str, Dict[str, Any]]:
    return {
        "R1": {"TYPE": "RGIBBS", "QNET": 2500.0, "WNET": 200.0, "CONV": 0.92, "EFF": 0.88},
        "HX1": {"TYPE": "HEATER", "QNET": -500.0, "WNET": -50.0, "CONV": None, "EFF": None},
    }


def test_extract_streams_basic() -> None:
    spec = _base_spec()
    aspen = mock_aspen_factory(_base_stream_values(), _base_block_values())
    streams_df = extract_results(aspen, spec)["streams"]

    expected_columns = {
        "stream_name",
        "temperature",
        "pressure",
        "mass_flow",
        "mole_flow",
        "CH3OH_mole_frac",
        "CH3OH_mass_frac",
        "H2O_mole_frac",
        "H2O_mass_frac",
    }
    assert expected_columns.issubset(set(streams_df.columns))
    assert len(streams_df) == 3
    meoh_row = streams_df.loc[streams_df["stream_name"] == "MEOH-PRO"].iloc[0]
    assert meoh_row["temperature"] == pytest.approx(35.0)
    assert meoh_row["CH3OH_mass_frac"] == pytest.approx(0.99)


def test_extract_streams_missing_node() -> None:
    spec = _base_spec()
    stream_values = _base_stream_values()
    stream_values["INT-1"].pop("PRES_OUT")
    stream_values["INT-1"]["MASSFRAC"].pop("CH3OH")
    aspen = mock_aspen_factory(stream_values, _base_block_values())
    streams_df = extract_results(aspen, spec)["streams"]

    int_row = streams_df.loc[streams_df["stream_name"] == "INT-1"].iloc[0]
    assert pd.isna(int_row["pressure"])
    assert pd.isna(int_row["CH3OH_mass_frac"])


def test_extract_blocks_basic() -> None:
    spec = _base_spec()
    aspen = mock_aspen_factory(_base_stream_values(), _base_block_values())
    blocks_df = extract_results(aspen, spec)["blocks"]

    expected_columns = {
        "block_name",
        "block_type",
        "duty_kw",
        "duty_mw",
        "net_work_kw",
        "conversion",
        "efficiency",
    }
    assert expected_columns.issubset(set(blocks_df.columns))
    r1 = blocks_df.loc[blocks_df["block_name"] == "R1"].iloc[0]
    assert r1["duty_raw"] == pytest.approx(2500.0)
    assert r1["duty_raw_unit"] == "CAL/SEC"
    assert r1["duty_source"] == "QNET"
    assert r1["duty_kw"] == pytest.approx(2500.0 * CAL_PER_SEC_TO_KW)
    assert r1["duty_mw"] == pytest.approx(2500.0 * CAL_PER_SEC_TO_MW)
    assert r1["net_work_raw"] == pytest.approx(200.0)
    assert r1["net_work_kw"] == pytest.approx(200.0 * CAL_PER_SEC_TO_KW)


def test_extract_radfrac_condenser_and_reboiler_duties_with_raw_provenance() -> None:
    spec = _base_spec()
    spec["blocks"].append({"name": "COL1", "type": "RADFRAC"})
    spec["flowsheet"].append({"block": "COL1", "inputs": ["INT-1"], "outputs": ["MEOH-PRO", "WASTE"]})
    spec["streams"].append({"name": "WASTE"})
    stream_values = _base_stream_values()
    stream_values["WASTE"] = {
        "TEMP_OUT": 60.0,
        "PRES_OUT": 2.08,
        "MASSFLMX": 5000.0,
        "MOLEFLMX": 30.0,
        "MOLEFRAC": {"CH3OH": 0.01, "H2O": 0.99},
        "MASSFRAC": {"CH3OH": 0.02, "H2O": 0.98},
    }
    block_values = _base_block_values()
    block_values["COL1"] = {"TYPE": "RADFRAC", "QCOND": -1000.0, "QREB": 2500.0}
    aspen = mock_aspen_factory(stream_values, block_values)

    results = extract_results(aspen, spec)
    col = results["blocks"].loc[results["blocks"]["block_name"] == "COL1"].iloc[0]

    assert col["condenser_duty_raw"] == pytest.approx(-1000.0)
    assert col["condenser_duty_raw_unit"] == "CAL/SEC"
    assert col["condenser_duty_source"] == "QCOND"
    assert col["condenser_duty_mw"] == pytest.approx(-1000.0 * CAL_PER_SEC_TO_MW)
    assert col["reboiler_duty_raw"] == pytest.approx(2500.0)
    assert col["reboiler_duty_source"] == "QREB"
    assert col["duty_raw"] == pytest.approx(3500.0)
    assert col["duty_source"] == "captured_sum_abs:QCOND+QREB"
    assert results["kpis"]["energy_consumption_mw"] == pytest.approx(6500.0 * CAL_PER_SEC_TO_MW)


def test_radfrac_captured_duties_override_placeholder_direct_duty() -> None:
    spec = _base_spec()
    spec["blocks"].append({"name": "COL1", "type": "RADFRAC"})
    spec["flowsheet"].append({"block": "COL1", "inputs": ["INT-1"], "outputs": ["MEOH-PRO", "WASTE"]})
    spec["streams"].append({"name": "WASTE"})
    stream_values = _base_stream_values()
    stream_values["WASTE"] = {
        "TEMP_OUT": 60.0,
        "PRES_OUT": 2.08,
        "MASSFLMX": 5000.0,
        "MOLEFLMX": 30.0,
        "MOLEFRAC": {"CH3OH": 0.01, "H2O": 0.99},
        "MASSFRAC": {"CH3OH": 0.02, "H2O": 0.98},
    }
    block_values = _base_block_values()
    block_values["COL1"] = {
        "TYPE": "RADFRAC",
        "DUTY": 1.0,
        "COND_DUTY": -1000.0,
        "REB_DUTY": 2500.0,
    }
    aspen = mock_aspen_factory(stream_values, block_values)

    results = extract_results(aspen, spec)
    col = results["blocks"].loc[results["blocks"]["block_name"] == "COL1"].iloc[0]

    assert col["duty_raw"] == pytest.approx(3500.0)
    assert col["duty_source"] == "captured_sum_abs:COND_DUTY+REB_DUTY"
    assert col["duty_mw"] == pytest.approx(3500.0 * CAL_PER_SEC_TO_MW)


def test_material_balance_calculation() -> None:
    spec = _base_spec()
    aspen = mock_aspen_factory(_base_stream_values(), _base_block_values())
    mat_df = extract_results(aspen, spec)["material_balance"]

    methanol = mat_df.loc[mat_df["component_id"] == "CH3OH"].iloc[0]
    assert methanol["input_kmol_hr"] == pytest.approx(40.0)
    assert methanol["output_kmol_hr"] == pytest.approx(76.0)
    assert methanol["closure_pct"] == pytest.approx(90.0)


def test_energy_balance_calculation() -> None:
    spec = _base_spec()
    aspen = mock_aspen_factory(_base_stream_values(), _base_block_values())
    energy_df = extract_results(aspen, spec)["energy_balance"]

    assert list(energy_df["block_name"]) == ["R1", "HX1", "TOTAL"]

    r1 = energy_df.loc[energy_df["block_name"] == "R1"].iloc[0]
    hx1 = energy_df.loc[energy_df["block_name"] == "HX1"].iloc[0]
    total = energy_df.loc[energy_df["block_name"] == "TOTAL"].iloc[0]

    assert r1["duty_raw"] == pytest.approx(2500.0)
    assert r1["duty_kw"] == pytest.approx(2500.0 * CAL_PER_SEC_TO_KW)
    assert hx1["duty_kw"] == pytest.approx(-500.0 * CAL_PER_SEC_TO_KW)
    assert total["duty_raw"] == pytest.approx(2000.0)
    assert total["duty_kw"] == pytest.approx(2000.0 * CAL_PER_SEC_TO_KW)
    assert total["duty_mw"] == pytest.approx(2000.0 * CAL_PER_SEC_TO_MW)


def test_energy_balance_calculation_summary_view() -> None:
    spec = _base_spec()
    aspen = mock_aspen_factory(_base_stream_values(), _base_block_values())
    energy_df = extract_results(aspen, spec, energy_balance_view="summary")["energy_balance"]

    heat_in = energy_df.loc[energy_df["category"] == "Heat Input", "value_mw"].iloc[0]
    heat_out = energy_df.loc[energy_df["category"] == "Heat Output", "value_mw"].iloc[0]
    net_work = energy_df.loc[energy_df["category"] == "Net Work", "value_mw"].iloc[0]

    assert heat_in == pytest.approx(2500.0 * CAL_PER_SEC_TO_MW)
    assert heat_out == pytest.approx(-500.0 * CAL_PER_SEC_TO_MW)
    assert net_work == pytest.approx(150.0 * CAL_PER_SEC_TO_MW)


def test_kpi_energy_consumption_uses_corrected_mw() -> None:
    spec = _base_spec()
    aspen = mock_aspen_factory(_base_stream_values(), _base_block_values())
    kpis = extract_results(aspen, spec)["kpis"]

    assert kpis["energy_consumption_mw"] == pytest.approx((2500.0 + 500.0) * CAL_PER_SEC_TO_MW)
    assert kpis["energy_unit_basis"]["raw_unit"] == "CAL/SEC"


def test_rplug_duty_uses_reactor_fallback_when_qnet_missing() -> None:
    spec = {
        "components": [{"id": "CH3OH", "name": "METHANOL"}],
        "streams": [{"name": "R-IN"}, {"name": "R-OUT"}],
        "blocks": [{"name": "B-SYN", "type": "RPLUG"}],
        "flowsheet": [{"block": "B-SYN", "inputs": ["R-IN"], "outputs": ["R-OUT"]}],
    }
    stream_values = {
        "R-IN": {
            "MASSFLMX": 100.0,
            "MOLEFLMX": 10.0,
            "MOLEFRAC": {"CH3OH": 0.0},
            "MASSFRAC": {"CH3OH": 0.0},
        },
        "R-OUT": {
            "MASSFLMX": 100.0,
            "MOLEFLMX": 10.0,
            "MOLEFRAC": {"CH3OH": 1.0},
            "MASSFRAC": {"CH3OH": 1.0},
        },
    }
    aspen = mock_aspen_factory(stream_values, {"B-SYN": {"TYPE": "RPLUG", "QREAC": 19918000.0}})

    blocks_df = extract_results(aspen, spec)["blocks"]
    syn = blocks_df.loc[blocks_df["block_name"] == "B-SYN"].iloc[0]

    assert syn["duty_source"] == "QREAC"
    assert syn["duty_raw"] == pytest.approx(19918000.0)
    assert syn["duty_mw"] == pytest.approx(19918000.0 * CAL_PER_SEC_TO_MW)


def test_kpi_production_rate() -> None:
    spec = _base_spec()
    aspen = mock_aspen_factory(_base_stream_values(), _base_block_values())
    kpis = extract_results(aspen, spec)["kpis"]
    assert kpis["production_rate_tpd"] == pytest.approx(2400.0)
    assert kpis["product_stream"] == "MEOH-PRO"
    assert kpis["product_total_tpd"] == pytest.approx(2400.0)
    assert kpis["product_component"] == "CH3OH"
    assert kpis["product_component_tpd"] == pytest.approx(2376.0)
    assert kpis["methanol_tpd"] == pytest.approx(2376.0)


def test_purity_expression_wt_pct() -> None:
    spec = _base_spec(with_purity=True, purity_expression="CH3OH wt% in MEOH-PRO")
    aspen = mock_aspen_factory(_base_stream_values(), _base_block_values())
    kpis = extract_results(aspen, spec)["kpis"]
    assert kpis["purity_fraction"] == pytest.approx(0.99)


def test_purity_expression_mol_pct() -> None:
    spec = _base_spec(with_purity=True, purity_expression="CH3OH mol% in MEOH-PRO")
    aspen = mock_aspen_factory(_base_stream_values(), _base_block_values())
    kpis = extract_results(aspen, spec)["kpis"]
    assert kpis["purity_fraction"] == pytest.approx(0.95)


def test_purity_expression_none() -> None:
    """When no purity expression is in the spec, purity_fraction must be None.

    Previously DEFAULT_PURITY_EXPRESSION = "CH3OH wt% in MEOH-PRO" was used as
    a fallback, which caused non-methanol processes to get a nonsensical purity.
    """
    spec = _base_spec(with_purity=False)
    aspen = mock_aspen_factory(_base_stream_values(), _base_block_values())
    kpis = extract_results(aspen, spec)["kpis"]
    assert kpis["purity_fraction"] is None


def test_purity_expression_defaults_when_purity_target_missing() -> None:
    """targets section present but no purity key → purity_fraction must be None."""
    spec = _base_spec(with_purity=False)
    spec["targets"] = {"production_rate_tpd": 1000.0, "tolerance": 0.01}
    aspen = mock_aspen_factory(_base_stream_values(), _base_block_values())
    kpis = extract_results(aspen, spec)["kpis"]
    assert kpis["purity_fraction"] is None


def test_yield_fraction_component_based_default() -> None:
    spec = _base_spec(with_purity=True, purity_expression="CH3OH wt% in MEOH-PRO")
    aspen = mock_aspen_factory(_base_stream_values(), _base_block_values())
    kpis = extract_results(aspen, spec)["kpis"]
    assert kpis["yield_fraction"] == pytest.approx((80.0 * 0.95) / (100.0 * 0.4))


def test_yield_fraction_uses_targets_yield_component_and_stream_selection() -> None:
    spec = _base_spec(with_purity=True, purity_expression="CH3OH wt% in MEOH-PRO")
    spec["streams"].insert(1, {"name": "FEED-B"})
    spec["flowsheet"] = [
        {"block": "R1", "inputs": ["FEED-A", "FEED-B"], "outputs": ["INT-1"]},
        {"block": "HX1", "inputs": ["INT-1"], "outputs": ["MEOH-PRO"]},
    ]
    spec["targets"] = {
        "purity": {"expression": "CH3OH wt% in MEOH-PRO"},
        "yield": {"component": "CH3OH", "stream": "INT-1", "feed_stream": "FEED-B"},
    }

    stream_values = _base_stream_values()
    stream_values["FEED-B"] = {
        "TEMP_OUT": 30.0,
        "PRES_OUT": 20.0,
        "MASSFLMX": 15000.0,
        "MOLEFLMX": 50.0,
        "MOLEFRAC": {"CH3OH": 0.2, "H2O": 0.8},
        "MASSFRAC": {"CH3OH": 0.18, "H2O": 0.82},
    }

    aspen = mock_aspen_factory(stream_values, _base_block_values())
    kpis = extract_results(aspen, spec)["kpis"]
    assert kpis["yield_fraction"] == pytest.approx((90.0 * 0.5) / (50.0 * 0.2))


def test_yield_fraction_none_when_component_composition_missing() -> None:
    spec = _base_spec(with_purity=True, purity_expression="CH3OH wt% in MEOH-PRO")
    stream_values = _base_stream_values()
    stream_values["MEOH-PRO"]["MOLEFRAC"].pop("CH3OH")
    aspen = mock_aspen_factory(stream_values, _base_block_values())
    kpis = extract_results(aspen, spec)["kpis"]
    assert kpis["yield_fraction"] is None


def test_synthesis_loop_diagnostics_report_selectivity_and_recycle_quality() -> None:
    spec = {
        "components": [
            {"id": "CH4", "name": "METHANE"},
            {"id": "CO", "name": "CO"},
            {"id": "CO2", "name": "CO2"},
            {"id": "H2", "name": "H2"},
            {"id": "CH3OH", "name": "METHANOL"},
            {"id": "H2O", "name": "WATER"},
        ],
        "streams": [{"name": "R-IN"}, {"name": "R-OUT"}, {"name": "MEOH-PRO"}],
        "blocks": [{"name": "B-SYN", "type": "RPLUG"}],
        "flowsheet": [{"block": "B-SYN", "inputs": ["R-IN"], "outputs": ["R-OUT"]}],
        "targets": {"purity": {"expression": "CH3OH wt% in MEOH-PRO"}},
        "process_defaults": {"product_stream": "MEOH-PRO"},
    }
    stream_values = {
        "R-IN": {
            "TEMP_OUT": 250.0,
            "PRES_OUT": 80.0,
            "MASSFLMX": 1000.0,
            "MOLEFLMX": 100.0,
            "MOLEFRAC": {"CH4": 0.1, "CO": 0.2, "CO2": 0.1, "H2": 0.6, "CH3OH": 0.0, "H2O": 0.0},
            "MASSFRAC": {"CH4": 0.1, "CO": 0.2, "CO2": 0.1, "H2": 0.6, "CH3OH": 0.0, "H2O": 0.0},
        },
        "R-OUT": {
            "TEMP_OUT": 250.0,
            "PRES_OUT": 80.0,
            "MASSFLMX": 1000.0,
            "MOLEFLMX": 95.0,
            "MOLEFRAC": {"CH4": 0.105, "CO": 0.1, "CO2": 0.12, "H2": 0.55, "CH3OH": 0.1, "H2O": 0.025},
            "MASSFRAC": {"CH4": 0.1, "CO": 0.1, "CO2": 0.12, "H2": 0.5, "CH3OH": 0.16, "H2O": 0.02},
        },
        "MEOH-PRO": {
            "TEMP_OUT": 40.0,
            "PRES_OUT": 1.5,
            "MASSFLMX": 200.0,
            "MOLEFLMX": 10.0,
            "MOLEFRAC": {"CH4": 0.0, "CO": 0.0, "CO2": 0.0, "H2": 0.0, "CH3OH": 0.95, "H2O": 0.05},
            "MASSFRAC": {"CH4": 0.0, "CO": 0.0, "CO2": 0.0, "H2": 0.0, "CH3OH": 0.99, "H2O": 0.01},
        },
    }
    block_values = {"B-SYN": {"TYPE": "RPLUG", "QNET": 1000.0}}
    aspen = mock_aspen_factory(stream_values, block_values)

    kpis = extract_results(aspen, spec)["kpis"]
    synthesis = kpis["synthesis_loop"]

    assert synthesis["available"] is True
    assert synthesis["co_conversion_fraction"] == pytest.approx((20.0 - 9.5) / 20.0)
    assert synthesis["methanol_formation_kmol_hr"] == pytest.approx(9.5)
    assert synthesis["methane_change_kmol_hr"] == pytest.approx(95.0 * 0.105 - 100.0 * 0.1)
    assert synthesis["inlet_stoichiometric_number"] == pytest.approx((60.0 - 10.0) / (20.0 + 10.0))


def test_identify_feed_product_streams() -> None:
    spec = {
        "flowsheet": [
            {"block": "B1", "inputs": ["FEED-1", "FEED-2"], "outputs": ["MID-1"]},
            {"block": "B2", "inputs": ["MID-1"], "outputs": ["MID-2"]},
            {"block": "B3", "inputs": ["MID-2"], "outputs": ["PROD", "VENT"]},
        ]
    }
    feed_streams, product_streams = _identify_feed_product_streams(spec)
    assert feed_streams == ["FEED-1", "FEED-2"]
    assert product_streams == ["PROD", "VENT"]


def test_extract_results_full() -> None:
    spec = _base_spec()
    aspen = mock_aspen_factory(_base_stream_values(), _base_block_values())
    results = extract_results(aspen, spec)

    assert set(results.keys()) == {
        "streams",
        "blocks",
        "material_balance",
        "energy_balance",
        "kpis",
        "diagnostics",
        "metadata",
    }
    assert isinstance(results["streams"], pd.DataFrame)
    assert isinstance(results["blocks"], pd.DataFrame)
    assert isinstance(results["material_balance"], pd.DataFrame)
    assert isinstance(results["energy_balance"], pd.DataFrame)
    assert isinstance(results["kpis"], dict)
    assert isinstance(results["diagnostics"], dict)
    assert isinstance(results["metadata"], dict)


def test_extract_results_no_crash_on_failed_sim() -> None:
    spec = _base_spec()
    aspen = mock_aspen_factory(
        stream_values={},
        block_values={},
        diagnostics={"PER_ERROR": 3, "NERROR": 2, "NWARN": 1},
    )
    results = extract_results(aspen, spec)

    assert set(results.keys()) == {
        "streams",
        "blocks",
        "material_balance",
        "energy_balance",
        "kpis",
        "diagnostics",
        "metadata",
    }
    assert results["diagnostics"]["convergence_status"] == "failed"
    assert results["kpis"]["convergence_status"] == "failed"


def test_pick_product_stream_generic_process_no_meoh() -> None:
    """_pick_product_stream must work for non-methanol processes.

    When there is no MEOH-PRO stream and no CH3OH column, the product should be
    identified from the spec's flowsheet topology (product streams = outputs that
    are not inputs of any block), picking the one with highest mass_flow.
    Previously the function returned None after failing to find MEOH-PRO and
    finding no CH3OH_mass_frac column.
    """
    from aspen_automation.extractor import extract_results

    spec: Dict[str, Any] = {
        "components": [
            {"id": "NH3", "name": "AMMONIA"},
            {"id": "H2", "name": "HYDROGEN"},
        ],
        "streams": [
            {"name": "H2-FEED"},
            {"name": "NH3-PROD"},
        ],
        "blocks": [{"name": "SYN-1", "type": "RGIBBS"}],
        "flowsheet": [
            {"block": "SYN-1", "inputs": ["H2-FEED"], "outputs": ["NH3-PROD"]},
        ],
        "targets": {"purity": {"expression": "NH3 wt% in NH3-PROD"}},
    }
    stream_values = {
        "H2-FEED": {
            "TEMP_OUT": 25.0,
            "PRES_OUT": 1.0,
            "MASSFLMX": 5000.0,
            "MOLEFLMX": 200.0,
            "MOLEFRAC": {"NH3": 0.0, "H2": 1.0},
            "MASSFRAC": {"NH3": 0.0, "H2": 1.0},
        },
        "NH3-PROD": {
            "TEMP_OUT": 30.0,
            "PRES_OUT": 1.0,
            "MASSFLMX": 4800.0,
            "MOLEFLMX": 180.0,
            "MOLEFRAC": {"NH3": 0.95, "H2": 0.05},
            "MASSFRAC": {"NH3": 0.94, "H2": 0.06},
        },
    }
    block_values = {"SYN-1": {"TYPE": "RGIBBS", "QNET": 1000.0}}
    aspen = mock_aspen_factory(stream_values, block_values)
    kpis = extract_results(aspen, spec)["kpis"]
    # NH3-PROD is the only product stream by topology; production_rate must be non-None
    assert kpis["production_rate_tpd"] is not None
    assert kpis["production_rate_tpd"] == pytest.approx(4800.0 * 24.0 / 1000.0)
    assert kpis["purity_fraction"] == pytest.approx(0.94)


def test_extract_results_uses_fallback_convergence_path() -> None:
    spec = _base_spec()
    aspen = mock_aspen_factory(
        _base_stream_values(),
        _base_block_values(),
        diagnostics={"ALT_PER_ERROR": 0, "ALT_NERROR": 0, "ALT_NWARN": 1},
    )

    results = extract_results(aspen, spec)

    assert results["diagnostics"]["convergence_status"] == "converged"
    assert results["diagnostics"]["per_error_path"] == r"\Data\Convergence\Batch-Options\Output\PER_ERROR"
    assert results["kpis"]["convergence_status"] == "converged"


# ---------------------------------------------------------------------------
# process_defaults integration tests
# ---------------------------------------------------------------------------

def test_purity_falls_back_to_process_defaults_expression() -> None:
    """When targets has no purity, process_defaults.purity_expression is used."""
    spec = _base_spec(with_purity=False)
    spec["process_defaults"] = {"purity_expression": "CH3OH wt% in MEOH-PRO"}
    aspen = mock_aspen_factory(_base_stream_values(), _base_block_values())
    kpis = extract_results(aspen, spec)["kpis"]
    assert kpis["purity_fraction"] == pytest.approx(0.99)


def test_targets_purity_takes_priority_over_process_defaults() -> None:
    """targets.purity.expression wins over process_defaults.purity_expression."""
    spec = _base_spec(with_purity=True, purity_expression="CH3OH mol% in MEOH-PRO")
    spec["process_defaults"] = {"purity_expression": "CH3OH wt% in MEOH-PRO"}
    aspen = mock_aspen_factory(_base_stream_values(), _base_block_values())
    kpis = extract_results(aspen, spec)["kpis"]
    assert kpis["purity_fraction"] == pytest.approx(0.95)  # mol%, not wt% 0.99


def test_process_defaults_product_stream_overrides_topology() -> None:
    """process_defaults.product_stream picks the named product even when topology has
    multiple candidates and another one has higher mass_flow.
    """
    spec = _base_spec(with_purity=False)
    # Two product streams: MEOH-PRO and WASTE-H2O both appear as flowsheet outputs
    # that are not consumed by any block.
    spec["streams"].append({"name": "WASTE-H2O"})
    spec["flowsheet"] = [
        {"block": "R1", "inputs": ["FEED-A"], "outputs": ["INT-1"]},
        {"block": "HX1", "inputs": ["INT-1"], "outputs": ["MEOH-PRO", "WASTE-H2O"]},
    ]
    # WASTE-H2O has higher mass_flow → topology-only would pick WASTE-H2O (800000 > 100000)
    spec["process_defaults"] = {"product_stream": "MEOH-PRO"}
    stream_values = _base_stream_values()
    stream_values["WASTE-H2O"] = {
        "TEMP_OUT": 45.0,
        "PRES_OUT": 1.2,
        "MASSFLMX": 800000.0,
        "MOLEFLMX": 50.0,
        "MOLEFRAC": {"CH3OH": 0.01, "H2O": 0.99},
        "MASSFRAC": {"CH3OH": 0.01, "H2O": 0.99},
    }
    aspen = mock_aspen_factory(stream_values, _base_block_values())
    kpis = extract_results(aspen, spec)["kpis"]
    # process_defaults.product_stream="MEOH-PRO" must override topology + mass_flow bias
    # MEOH-PRO mass_flow=100000 kg/hr → 2400 tpd
    assert kpis["production_rate_tpd"] == pytest.approx(100000.0 * 24.0 / 1000.0)


def test_blank_separator_output_is_inferred_by_mass_closure() -> None:
    spec = {
        "components": [
            {"id": "CH3OH", "name": "METHANOL"},
            {"id": "H2O", "name": "WATER"},
        ],
        "streams": [{"name": "CRUDE-ME"}, {"name": "MEOH-PRO"}, {"name": "WASTE-H2O"}],
        "blocks": [{"name": "B-DIST", "type": "SEP"}],
        "flowsheet": [{"block": "B-DIST", "inputs": ["CRUDE-ME"], "outputs": ["MEOH-PRO", "WASTE-H2O"]}],
        "process_defaults": {"product_stream": "MEOH-PRO"},
    }
    stream_values = {
        "CRUDE-ME": {
            "MASSFLMX": 100.0,
            "MOLEFLMX": 10.0,
            "MOLEFRAC": {"CH3OH": 0.7, "H2O": 0.3},
            "MASSFRAC": {"CH3OH": 0.7, "H2O": 0.3},
        },
        "MEOH-PRO": {
            "MASSFLMX": 70.0,
            "MOLEFLMX": 7.0,
            "MOLEFRAC": {"CH3OH": 1.0, "H2O": 0.0},
            "MASSFRAC": {"CH3OH": 1.0, "H2O": 0.0},
        },
        "WASTE-H2O": {},
    }
    aspen = mock_aspen_factory(stream_values, {"B-DIST": {"TYPE": "SEP"}})

    results = extract_results(aspen, spec)
    streams_df = results["streams"]
    waste = streams_df.loc[streams_df["stream_name"] == "WASTE-H2O"].iloc[0]

    assert waste["extraction_status"] == "inferred_by_block_closure"
    assert waste["extraction_source"] == "B-DIST"
    assert waste["mass_flow"] == pytest.approx(30.0)
    assert waste["CH3OH_mass_frac"] == pytest.approx(0.0)
    assert waste["H2O_mass_frac"] == pytest.approx(1.0)
    assert pd.isna(waste["mole_flow"])
    assert results["diagnostics"]["stream_extraction"]["inferred_streams"][0]["stream_name"] == "WASTE-H2O"
    assert results["diagnostics"]["terminal_mass_closure"]["status"] == "closed"


def test_blank_radfrac_terminal_product_is_not_inferred() -> None:
    spec = {
        "components": [
            {"id": "CH3OH", "name": "METHANOL"},
            {"id": "H2O", "name": "WATER"},
        ],
        "streams": [{"name": "CRUDE-LP"}, {"name": "MEOH-PRO"}, {"name": "WASTE-H2O"}],
        "blocks": [{"name": "B-DIST", "type": "RADFRAC"}],
        "flowsheet": [{"block": "B-DIST", "inputs": ["CRUDE-LP"], "outputs": ["MEOH-PRO", "WASTE-H2O"]}],
        "process_defaults": {"product_stream": "MEOH-PRO"},
    }
    stream_values = {
        "CRUDE-LP": {
            "MASSFLMX": 100.0,
            "MOLEFLMX": 10.0,
            "MOLEFRAC": {"CH3OH": 0.7, "H2O": 0.3},
            "MASSFRAC": {"CH3OH": 0.7, "H2O": 0.3},
        },
        "MEOH-PRO": {
            "MASSFLMX": 70.0,
            "MOLEFLMX": 7.0,
            "MOLEFRAC": {"CH3OH": 1.0, "H2O": 0.0},
            "MASSFRAC": {"CH3OH": 1.0, "H2O": 0.0},
        },
        "WASTE-H2O": {},
    }
    aspen = mock_aspen_factory(stream_values, {"B-DIST": {"TYPE": "RADFRAC"}})

    results = extract_results(aspen, spec)

    stream_extraction = results["diagnostics"]["stream_extraction"]
    assert stream_extraction["inferred_streams"] == []
    assert "WASTE-H2O" in stream_extraction["blank_streams_after_inference"]
    assert stream_extraction["blank_radfrac_product_streams"] == [
        {"block_name": "B-DIST", "stream_name": "WASTE-H2O"}
    ]
    waste = results["streams"].loc[results["streams"]["stream_name"] == "WASTE-H2O"].iloc[0]
    assert waste["extraction_status"] == "missing"


def test_uninferable_blank_stream_is_reported_in_diagnostics() -> None:
    spec = _base_spec(with_purity=False)
    spec["streams"].append({"name": "WASTE-H2O"})
    spec["flowsheet"] = [
        {"block": "R1", "inputs": ["FEED-A"], "outputs": ["INT-1"]},
        {"block": "HX1", "inputs": ["INT-1"], "outputs": ["MEOH-PRO", "WASTE-H2O"]},
    ]
    stream_values = _base_stream_values()
    stream_values["WASTE-H2O"] = {}
    aspen = mock_aspen_factory(stream_values, _base_block_values())

    results = extract_results(aspen, spec)

    stream_extraction = results["diagnostics"]["stream_extraction"]
    assert stream_extraction["inferred_streams"] == []
    assert "WASTE-H2O" in stream_extraction["blank_streams_after_inference"]
    assert results["diagnostics"]["terminal_mass_closure"]["status"] == "incomplete"


def test_process_defaults_convergence_block_used_when_per_error_absent() -> None:
    """process_defaults.convergence_block is queried when PER_ERROR paths return None.

    Note: mock_aspen_factory uses `diagnostics or default`, so we pass a non-empty
    dict that omits PER_ERROR to prevent the fallback to the default PER_ERROR=0.
    """
    spec = _base_spec()
    spec["process_defaults"] = {"convergence_block": "B-ATR"}
    block_values = _base_block_values()
    block_values["B-ATR"] = {"BLKSTAT": 0}  # converged
    # Non-empty diagnostics dict with no PER_ERROR key: all per_error paths return None.
    aspen = mock_aspen_factory(
        _base_stream_values(),
        block_values,
        diagnostics={"NERROR": 0, "NWARN": 0},
    )
    results = extract_results(aspen, spec)
    assert results["diagnostics"]["convergence_status"] == "converged"
    assert results["kpis"]["convergence_status"] == "converged"
