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
