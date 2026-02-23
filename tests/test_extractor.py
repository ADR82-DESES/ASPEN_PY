import sys
from unittest.mock import MagicMock, patch
import pytest
import pandas as pd
import datetime

# Mock win32com before any imports
sys.modules['win32com'] = MagicMock()
sys.modules['win32com.client'] = MagicMock()


from aspen_automation.extractor import (
    _safe_node_value,
    _get_element_names,
    extract_stream_properties,
    extract_block_performance,
    parse_purity_expression,
    evaluate_purity,
    calculate_material_balance,
    calculate_energy_balance,
    calculate_kpis,
    extract_diagnostics,
    extract_results
)
from aspen_automation.exceptions import ExtractionError
from aspen_automation.schema import PlantSpecification

@pytest.fixture
def mock_aspen():
    aspen = MagicMock()
    mock_node = MagicMock()
    mock_node.Value = 1.0
    aspen.Tree.FindNode.return_value = mock_node
    return aspen

def test_safe_node_value_returns_value(mock_aspen):
    mock_node = MagicMock()
    mock_node.Value = 42.0
    mock_aspen.Tree.FindNode.return_value = mock_node
    
    val = _safe_node_value(mock_aspen, r"path\to\node")
    assert val == 42.0

def test_safe_node_value_returns_none_on_missing(mock_aspen):
    mock_aspen.Tree.FindNode.return_value = None
    val = _safe_node_value(mock_aspen, r"path\to\missing")
    assert val is None

def test_safe_node_value_returns_none_on_exception(mock_aspen):
    mock_aspen.Tree.FindNode.side_effect = Exception("COM error")
    val = _safe_node_value(mock_aspen, r"path\to\error")
    assert val is None

def test_extract_stream_properties_columns(mock_aspen):
    df = extract_stream_properties(mock_aspen, ["S1", "S2"], ["CH4", "H2O"])
    
    assert "stream_name" in df.columns
    assert "temperature" in df.columns
    assert "CH4_mole_frac" in df.columns
    assert "H2O_mass_frac" in df.columns
    assert len(df) == 2

def test_extract_stream_properties_empty(mock_aspen):
    df = extract_stream_properties(mock_aspen, [], ["CH4"])
    assert len(df) == 0

def test_extract_block_performance_columns(mock_aspen):
    df = extract_block_performance(mock_aspen, ["B1"])
    assert "block_name" in df.columns
    assert "duty" in df.columns
    assert "conversion" in df.columns
    assert "efficiency" in df.columns
    assert len(df) == 1

def test_parse_purity_expression_default():
    comp, basis, stream = parse_purity_expression("CH3OH wt% in MEOH-PRO")
    assert comp == "CH3OH"
    assert basis.lower() == "wt%"
    assert stream == "MEOH-PRO"

def test_parse_purity_expression_mol():
    comp, basis, stream = parse_purity_expression("H2O mol% in WATER-OUT")
    assert comp == "H2O"
    assert basis.lower() == "mol%"
    assert stream == "WATER-OUT"

def test_parse_purity_expression_invalid():
    with pytest.raises(ValueError, match="Invalid purity expression"):
        parse_purity_expression("CH3OH mass FLOW WATER")

def test_evaluate_purity_mass_basis(mock_aspen):
    val = evaluate_purity(mock_aspen, "CH3OH wt% in S1")
    # The default mock_node.Value is 1.0
    assert val == 1.0
    mock_aspen.Tree.FindNode.assert_called_with(r"\Data\Streams\S1\Output\MASSFRAC\MIXED\CH3OH")

def test_evaluate_purity_mole_basis(mock_aspen):
    val = evaluate_purity(mock_aspen, "CH3OH mol% in S1")
    assert val == 1.0
    mock_aspen.Tree.FindNode.assert_called_with(r"\Data\Streams\S1\Output\MOLEFRAC\MIXED\CH3OH")

def test_calculate_material_balance_closure(mock_aspen):
    # If all nodes return 1.0 flow and 1.0 frac.
    # Total_in = 1.0*1.0 = 1.0. Total_out = 1.0*1.0 = 1.0. Closure = 0%
    spec = {
        "components": [{"id": "C1"}],
        "flowsheet": [
            {"inputs": ["FEED"], "outputs": ["PROD"]}
        ]
    }
    df = calculate_material_balance(mock_aspen, spec)
    assert df.iloc[0]["component"] == "C1"
    assert df.iloc[0]["input_kmol_hr"] == 1.0
    assert df.iloc[0]["output_kmol_hr"] == 1.0
    assert df.iloc[0]["closure_%"] == 0.0

def test_calculate_energy_balance_sum(mock_aspen):
    spec = {
        "blocks": [{"name": "B1"}, {"name": "B2"}]
    }
    df = calculate_energy_balance(mock_aspen, spec)
    assert len(df) == 3 # 2 blocks + TOTAL
    # mock_node.Value = 1.0 -> 1.0 + 1.0 = 2.0
    assert df.iloc[-1]["block_name"] == "TOTAL"
    assert df.iloc[-1]["duty_kw"] == 2.0

def test_calculate_kpis_converged(mock_aspen):
    def mock_find_node_converged(path):
        m = MagicMock()
        if path.endswith("PER_ERROR"):
            m.Value = 0
            return m
        m.Value = 1.0
        return m
    mock_aspen.Tree.FindNode.side_effect = mock_find_node_converged
    
    spec = {"targets": {"production_stream": "P1", "purity": {"expression": "C1 wt% in P1"}}}
    
    streams_df = pd.DataFrame([{"stream_name": "P1", "mass_flow": 1000.0, "mole_flow": 50.0}])
    blocks_df = pd.DataFrame([{"block_name": "B1", "duty_kw": 2000.0}, {"block_name": "TOTAL", "duty_kw": 2000.0}])
    
    kpis = calculate_kpis(mock_aspen, spec, streams_df, blocks_df)
    assert kpis["convergence_status"] == "converged"
    # mass_flow * 24 / 1000
    assert kpis["production_rate_tpd"] == 24.0
    # duty_kw / 1000
    assert kpis["energy_consumption_mw"] == 2.0

def test_calculate_kpis_failed(mock_aspen):
    def mock_find_node_failed(path):
        m = MagicMock()
        if path.endswith("PER_ERROR"):
            m.Value = 2
            return m
        m.Value = 1.0
        return m
    mock_aspen.Tree.FindNode.side_effect = mock_find_node_failed
    
    kpis = calculate_kpis(mock_aspen, {}, pd.DataFrame(), pd.DataFrame())
    assert kpis["convergence_status"] == "failed"

def test_extract_diagnostics_keys(mock_aspen):
    diags = extract_diagnostics(mock_aspen)
    assert "per_error" in diags
    assert "convergence_status" in diags
    assert "warning_count" in diags
    assert "error_count" in diags

@patch("aspen_automation.extractor._get_element_names")
def test_extract_results_structure(mock_get_element_names, mock_aspen):
    mock_get_element_names.side_effect = [["S1"], ["B1"]]
    
    spec = {"components": [{"id": "C1"}], "blocks": [{"name": "B1"}], "flowsheet": [{"inputs": ["S1"], "outputs": ["S2"]}]}
    res = extract_results(mock_aspen, spec)
    
    assert "streams" in res
    assert "blocks" in res
    assert "material_balance" in res
    assert "energy_balance" in res
    assert "kpis" in res
    assert "diagnostics" in res
    assert "metadata" in res

@patch("aspen_automation.extractor._get_element_names")
def test_extract_results_metadata(mock_get_element_names, mock_aspen):
    mock_get_element_names.side_effect = [["S1", "S2"], ["B1", "B2", "B3"]]
    
    res = extract_results(mock_aspen, {})
    
    assert "extracted_at" in res["metadata"]
    assert res["metadata"]["stream_count"] == 2
    assert res["metadata"]["block_count"] == 3
