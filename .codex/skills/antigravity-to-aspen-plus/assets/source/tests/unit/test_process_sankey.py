import pandas as pd

from aspen_automation.process_sankey import sankey_mass_balance

SPEC = {
    "blocks": [{"name": "RX", "type": "RGIBBS"}, {"name": "SEP", "type": "FLASH2"}],
    "flowsheet": [
        {"block": "RX", "inputs": ["FEED"], "outputs": ["RXOUT"]},
        {"block": "SEP", "inputs": ["RXOUT"], "outputs": ["PROD", "OFFGAS"]},
    ],
}


def _data():
    return {"streams": pd.DataFrame({
        "stream_name": ["FEED", "RXOUT", "PROD", "OFFGAS"],
        "mass_flow": [100.0, 100.0, 60.0, 40.0],
    })}


def test_sankey_mass_balance_is_sankey_with_flow_values():
    fig = sankey_mass_balance(_data(), SPEC)
    assert fig.data[0].type == "sankey"
    labels = list(fig.data[0].node.label)
    # blocks present plus a feed terminal and product/purge terminals
    assert "RX" in labels and "SEP" in labels
    assert any(l.startswith("FEED") for l in labels)
    # link values equal the stream mass flows
    assert sorted(fig.data[0].link.value) == [40.0, 60.0, 100.0, 100.0]


def test_sankey_mass_balance_empty_streams_is_blank():
    fig = sankey_mass_balance({"streams": pd.DataFrame()}, SPEC)
    assert fig.data[0].type == "sankey"
    assert len(fig.data[0].link.value) == 0


from aspen_automation.process_sankey import sankey_energy_balance


def test_sankey_energy_balance_routes_by_sign():
    data = {"blocks": pd.DataFrame({
        "block_name": ["B-HEAT", "B-COOL", "B-COMP"],
        "duty_kw": [500.0, -300.0, 0.0],
        "net_work_kw": [0.0, 0.0, 200.0],
    })}
    fig = sankey_energy_balance(data)
    assert fig.data[0].type == "sankey"
    labels = list(fig.data[0].node.label)
    assert "Utilities" in labels and "Heat removed" in labels and "Work" in labels
    # one endothermic (Utilities->B-HEAT), one exothermic (B-COOL->Heat removed), one work
    assert sorted(fig.data[0].link.value) == [200.0, 300.0, 500.0]


def test_sankey_energy_balance_empty_blocks_is_blank():
    fig = sankey_energy_balance({"blocks": pd.DataFrame()})
    assert fig.data[0].type == "sankey"
    assert len(fig.data[0].link.value) == 0


def test_sankey_mass_balance_fans_out_to_all_consumers():
    # A stream feeding two blocks must produce a link into BOTH (no silent drop).
    spec = {
        "blocks": [{"name": "A", "type": "X"}, {"name": "B", "type": "X"}, {"name": "C", "type": "X"}],
        "flowsheet": [
            {"block": "A", "inputs": ["FEED"], "outputs": ["S"]},
            {"block": "B", "inputs": ["S"], "outputs": []},
            {"block": "C", "inputs": ["S"], "outputs": []},
        ],
    }
    data = {"streams": pd.DataFrame({"stream_name": ["FEED", "S"], "mass_flow": [10.0, 8.0]})}
    fig = sankey_mass_balance(data, spec)
    labels = list(fig.data[0].node.label)
    idx = {label: i for i, label in enumerate(labels)}
    links = set(zip(fig.data[0].link.source, fig.data[0].link.target))
    assert (idx["A"], idx["B"]) in links
    assert (idx["A"], idx["C"]) in links


def test_sankey_mass_balance_splits_by_species():
    from aspen_automation.species_colors import species_color

    spec = {"blocks": [{"name": "RX", "type": "X"}],
            "flowsheet": [{"block": "RX", "inputs": ["FEED"], "outputs": ["PROD"]}]}
    data = {"streams": pd.DataFrame({
        "stream_name": ["FEED", "PROD"],
        "mass_flow": [100.0, 100.0],
        "CH4_mass_frac": [0.8, 0.0],
        "H2O_mass_frac": [0.2, 1.0],
    })}
    fig = sankey_mass_balance(data, spec)
    sankey = fig.data[0]
    # FEED(100) -> CH4 80 + H2O 20 ; PROD(100) -> H2O 100 (CH4 frac 0 skipped)
    assert sorted(sankey.link.value) == [20.0, 80.0, 100.0]
    assert species_color("CH4") in list(sankey.link.color)
    assert species_color("H2O") in list(sankey.link.color)
    # hidden legend traces exist for the species present
    legend_names = {trace.name for trace in fig.data[1:]}
    assert legend_names == {"CH4", "H2O"}


def test_stream_styles_flow_and_dominant_species():
    from aspen_automation.process_sankey import stream_styles

    streams = pd.DataFrame({
        "stream_name": ["FEED", "PROD"],
        "mass_flow": [100.0, 50.0],
        "CH4_mass_frac": [0.8, 0.1],
        "H2O_mass_frac": [0.2, 0.9],
    })
    flow, dominant = stream_styles(streams)
    assert flow == {"FEED": 100.0, "PROD": 50.0}
    assert dominant == {"FEED": "CH4", "PROD": "H2O"}


def test_stream_styles_empty_is_blank():
    from aspen_automation.process_sankey import stream_styles

    flow, dominant = stream_styles(pd.DataFrame())
    assert flow == {} and dominant == {}
