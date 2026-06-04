from aspen_automation.dashboard import build_flowsheet_mermaid


def test_build_flowsheet_mermaid_nodes_edges_and_terminals():
    spec = {
        "blocks": [
            {"name": "RX", "type": "RSTOIC"},
            {"name": "SEP", "type": "SEP"},
        ],
        "flowsheet": [
            {"block": "RX", "inputs": ["FEED", "RECYCLE"], "outputs": ["RXOUT"]},
            {"block": "SEP", "inputs": ["RXOUT"], "outputs": ["PRODUCT", "RECYCLE"]},
        ],
    }
    mermaid = build_flowsheet_mermaid(spec)

    assert mermaid.startswith("graph LR")
    # block nodes with type labels
    assert 'RX["RX (RSTOIC)"]' in mermaid
    assert 'SEP["SEP (SEP)"]' in mermaid
    # external feed becomes a terminal feeding RX
    assert 'feed_FEED(["FEED"]) -->|FEED| RX' in mermaid
    # internal stream RX -> SEP
    assert "RX -->|RXOUT| SEP" in mermaid
    # product has no consumer -> terminal out node
    assert 'SEP -->|PRODUCT| out_PRODUCT(["PRODUCT"])' in mermaid
    # recycle goes back into RX
    assert "SEP -->|RECYCLE| RX" in mermaid


def test_build_flowsheet_mermaid_empty_spec():
    assert build_flowsheet_mermaid({}) == "graph LR"


import json as _json

from aspen_automation.dashboard import collect_dashboard_data


def _seed_results_dir(tmp_path):
    (tmp_path / "kpis.json").write_text(
        _json.dumps({"methanol_tpd": 9812.0, "synthesis_loop": {"co_conversion_fraction": 0.34}}),
        encoding="utf-8",
    )
    (tmp_path / "acceptance.json").write_text(_json.dumps({"passed": True}), encoding="utf-8")
    (tmp_path / "streams.csv").write_text(
        "stream_name,temperature,CH4_mole_frac,H2_mole_frac\nFEED,25,0.9,0.1\n",
        encoding="utf-8",
    )
    return tmp_path


def test_collect_dashboard_data_reads_artifacts(tmp_path):
    results_dir = _seed_results_dir(tmp_path)
    spec = {"metadata": {"title": "T"}, "components": [{"id": "CH4"}], "flowsheet": [], "blocks": []}

    data = collect_dashboard_data(results_dir, spec)

    assert data["kpis"]["methanol_tpd"] == 9812.0
    assert data["acceptance"]["passed"] is True
    assert list(data["streams"]["stream_name"]) == ["FEED"]
    assert data["metadata"]["title"] == "T"
    assert data["flowsheet_mermaid"].startswith("graph LR")


def test_collect_dashboard_data_missing_files_are_empty(tmp_path):
    data = collect_dashboard_data(tmp_path, None)

    assert data["kpis"] == {}
    assert data["acceptance"] == {}
    assert data["streams"].empty
    assert data["flowsheet_mermaid"] == ""


from aspen_automation.dashboard import figure_kpis, figure_synthesis_loop

import pandas as pd


def test_figure_kpis_is_gauge_with_methanol_value():
    data = {"kpis": {"methanol_tpd": 9812.0}}
    fig = figure_kpis(data)
    assert fig.data[0].type == "indicator"
    assert fig.data[0].value == 9812.0
    assert fig.data[0].gauge.axis.range == (0, 10000)


def test_figure_synthesis_loop_bar_labels():
    data = {"kpis": {"synthesis_loop": {
        "co_conversion_fraction": 0.34,
        "co2_conversion_fraction": 0.12,
        "h2_consumption_fraction": 0.40,
    }}}
    fig = figure_synthesis_loop(data)
    assert fig.data[0].type == "bar"
    assert list(fig.data[0].x) == ["CO conv", "CO2 conv", "H2 use"]
    assert list(fig.data[0].y) == [0.34, 0.12, 0.40]


from aspen_automation.dashboard import (
    figure_balances,
    figure_energy,
    figure_stream_composition,
)


def test_figure_stream_composition_one_trace_per_component():
    data = {"streams": pd.DataFrame({
        "stream_name": ["FEED", "PROD"],
        "CH4_mole_frac": [0.9, 0.0],
        "H2_mole_frac": [0.1, 0.2],
    })}
    fig = figure_stream_composition(data)
    names = sorted(trace.name for trace in fig.data)
    assert names == ["CH4", "H2"]
    assert fig.layout.barmode == "stack"


def test_figure_stream_composition_empty_is_blank_figure():
    fig = figure_stream_composition({"streams": pd.DataFrame()})
    assert len(fig.data) == 0


def test_figure_balances_in_out_traces():
    data = {"material_balance": pd.DataFrame({
        "component": ["CH4", "H2"],
        "input_kmol_hr": [10.0, 5.0],
        "output_kmol_hr": [9.0, 5.0],
    })}
    fig = figure_balances(data)
    names = sorted(trace.name for trace in fig.data)
    assert names == ["in", "out"]


def test_figure_energy_per_block_duty_bars():
    data = {"blocks": pd.DataFrame({
        "block_name": ["B-ATR", "B-COOL"],
        "duty_kw": [1200.0, -800.0],
    })}
    fig = figure_energy(data)
    assert fig.data[0].type == "bar"
    assert list(fig.data[0].x) == ["B-ATR", "B-COOL"]
    assert list(fig.data[0].y) == [1200.0, -800.0]


from aspen_automation.dashboard import render_mermaid_html, kpi_cards_html


def test_render_mermaid_html_wraps_diagram_in_iframe():
    html = render_mermaid_html("graph LR\n A-->B")
    assert "<iframe" in html.data
    assert "srcdoc=" in html.data
    assert "graph LR" in html.data
    assert "mermaid" in html.data


def test_kpi_cards_html_contains_values():
    data = {"kpis": {
                "methanol_tpd": 9812,
                "convergence_status": "converged",
                "product_stream": "MEOH",
                "synthesis_loop": {
                    "inlet_stoichiometric_number": 1.97,
                    "inlet_ch4_mole_frac": 0.02,
                    "inlet_co2_mole_frac": 0.05,
                },
            },
            "acceptance": {"passed": True}}
    html = kpi_cards_html(data)
    assert "9812" in html
    assert "MEOH" in html
    assert "PASS" in html
    # synthesis-loop SN + recycle surfaced as cards (with SN target band noted)
    assert "1.97" in html
    assert "1.8" in html and "2.2" in html
    assert "0.02" in html


from aspen_automation.dashboard import build_dashboard_html, save_dashboard_html


def test_build_dashboard_html_contains_sections():
    data = {
        "metadata": {"title": "Methanol Plant"},
        "kpis": {"methanol_tpd": 9812, "product_stream": "MEOH"},
        "acceptance": {"passed": True},
        "streams": pd.DataFrame({"stream_name": ["FEED"], "CH4_mole_frac": [1.0]}),
        "material_balance": pd.DataFrame({"component": ["CH4"], "input_kmol_hr": [1.0], "output_kmol_hr": [1.0]}),
        "flowsheet_mermaid": "graph LR\n A-->B",
    }
    html = build_dashboard_html(data, [figure_kpis(data)])
    assert "Methanol Plant" in html
    assert "graph LR" in html
    assert "plotly" in html.lower()
    assert "MEOH" in html


def test_save_dashboard_html_writes_file(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    _seed_results_dir(results_dir)
    out = save_dashboard_html(results_dir, tmp_path, spec={"metadata": {"title": "X"}, "components": [{"id": "CH4"}]})
    assert out == tmp_path / "dashboard.html"
    assert out.is_file()
    assert "X" in out.read_text(encoding="utf-8")


import aspen_automation


def test_dashboard_symbols_exported():
    assert hasattr(aspen_automation, "display_dashboard")
    assert hasattr(aspen_automation, "collect_dashboard_data")
    assert hasattr(aspen_automation, "build_flowsheet_mermaid")
    assert hasattr(aspen_automation, "save_dashboard_html")
