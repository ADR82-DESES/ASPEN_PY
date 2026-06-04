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
