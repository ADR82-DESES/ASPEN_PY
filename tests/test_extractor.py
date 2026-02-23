from __future__ import annotations

import sys
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pandas as pd
import pytest

# Keep package imports stable on non-Windows CI.
sys.modules["win32com"] = MagicMock()
sys.modules["win32com.client"] = MagicMock()

from aspen_automation.extractor import _identify_feed_product_streams, extract_results


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
        if path == r"\Data\Results Summary\Run-Status\Output\NERROR":
            return _node(diagnostics.get("NERROR"))
        if path == r"\Data\Results Summary\Run-Status\Output\NWARN":
            return _node(diagnostics.get("NWARN"))

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
    assert r1["duty_kw"] == pytest.approx(2500.0)
    assert r1["duty_mw"] == pytest.approx(2.5)


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

    assert r1["duty_kw"] == pytest.approx(2500.0)
    assert hx1["duty_kw"] == pytest.approx(-500.0)
    assert total["duty_kw"] == pytest.approx(2000.0)
    assert total["duty_mw"] == pytest.approx(2.0)


def test_energy_balance_calculation_summary_view() -> None:
    spec = _base_spec()
    aspen = mock_aspen_factory(_base_stream_values(), _base_block_values())
    energy_df = extract_results(aspen, spec, energy_balance_view="summary")["energy_balance"]

    heat_in = energy_df.loc[energy_df["category"] == "Heat Input", "value_mw"].iloc[0]
    heat_out = energy_df.loc[energy_df["category"] == "Heat Output", "value_mw"].iloc[0]
    net_work = energy_df.loc[energy_df["category"] == "Net Work", "value_mw"].iloc[0]

    assert heat_in == pytest.approx(2.5)
    assert heat_out == pytest.approx(-0.5)
    assert net_work == pytest.approx(0.15)


def test_kpi_production_rate() -> None:
    spec = _base_spec()
    aspen = mock_aspen_factory(_base_stream_values(), _base_block_values())
    kpis = extract_results(aspen, spec)["kpis"]
    assert kpis["production_rate_tpd"] == pytest.approx(2400.0)


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
    spec = _base_spec(with_purity=False)
    aspen = mock_aspen_factory(_base_stream_values(), _base_block_values())
    kpis = extract_results(aspen, spec)["kpis"]
    assert kpis["purity_fraction"] == pytest.approx(0.99)


def test_purity_expression_defaults_when_purity_target_missing() -> None:
    spec = _base_spec(with_purity=False)
    spec["targets"] = {"production_rate_tpd": 1000.0, "tolerance": 0.01}
    aspen = mock_aspen_factory(_base_stream_values(), _base_block_values())
    kpis = extract_results(aspen, spec)["kpis"]
    assert kpis["purity_fraction"] == pytest.approx(0.99)


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
