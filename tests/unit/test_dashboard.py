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
    (tmp_path / "blocks.csv").write_text(
        "block_name,duty_kw,net_work_kw\nRX,500,0\n", encoding="utf-8")
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


import aspen_automation


def test_dashboard_symbols_exported():
    assert hasattr(aspen_automation, "display_dashboard")
    assert hasattr(aspen_automation, "collect_dashboard_data")
    assert hasattr(aspen_automation, "build_flowsheet_mermaid")
    assert hasattr(aspen_automation, "save_dashboard_figures")
    assert hasattr(aspen_automation, "build_pfd_svg")
    assert hasattr(aspen_automation, "sankey_mass_balance")
    assert hasattr(aspen_automation, "sankey_energy_balance")
    assert not hasattr(aspen_automation, "save_dashboard_html")


def test_collect_dashboard_data_non_dict_json_root_degrades(tmp_path):
    # A corrupt artifact whose JSON root is an array/scalar must not break the
    # "never raises" contract: it should degrade to an empty dict, and
    # downstream consumers must not raise on the degraded data.
    (tmp_path / "kpis.json").write_text("[1, 2, 3]", encoding="utf-8")
    (tmp_path / "acceptance.json").write_text("true", encoding="utf-8")

    data = collect_dashboard_data(tmp_path, None)

    assert data["kpis"] == {}
    assert data["acceptance"] == {}
    kpi_cards_html(data)


from aspen_automation.dashboard import build_dashboard_html, save_dashboard_figures


def test_build_dashboard_html_embeds_pfd_and_sankeys(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    _seed_results_dir(results_dir)
    spec = {
        "metadata": {"title": "Methanol Plant"},
        "components": [{"id": "CH4"}],
        "blocks": [{"name": "RX", "type": "RGIBBS"}],
        "flowsheet": [{"block": "RX", "inputs": ["FEED"], "outputs": ["PROD"]}],
    }
    data = collect_dashboard_data(results_dir, spec)
    html = build_dashboard_html(data, spec)
    assert "Methanol Plant" in html
    assert "sankey" in html.lower()        # plotly sankey embedded
    assert "svg" in html.lower()           # PFD svg/mermaid embedded


def test_save_dashboard_figures_writes_files(tmp_path):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    _seed_results_dir(results_dir)
    spec = {"metadata": {"title": "X"}, "components": [{"id": "CH4"}],
            "blocks": [{"name": "RX", "type": "RGIBBS"}],
            "flowsheet": [{"block": "RX", "inputs": ["FEED"], "outputs": ["PROD"]}]}
    paths = save_dashboard_figures(results_dir, tmp_path, spec)
    figdir = tmp_path / "figures"
    assert (figdir / "flowsheet_pfd.svg").is_file()
    assert (figdir / "mass_balance_sankey.svg").is_file()
    assert any(str(p).endswith("synthesis_loop.svg") for p in paths.values())
