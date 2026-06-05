from aspen_automation.flowsheet_graph import stream_endpoints, block_edges

SPEC = {
    "blocks": [{"name": "RX", "type": "RSTOIC"}, {"name": "SEP", "type": "SEP"}],
    "flowsheet": [
        {"block": "RX", "inputs": ["FEED", "RECYCLE"], "outputs": ["RXOUT"]},
        {"block": "SEP", "inputs": ["RXOUT"], "outputs": ["PRODUCT", "RECYCLE"]},
    ],
}


def test_stream_endpoints_producers_and_consumers():
    producers, consumers = stream_endpoints(SPEC)
    assert producers == {"RXOUT": "RX", "PRODUCT": "SEP", "RECYCLE": "SEP"}
    assert consumers == {"FEED": ["RX"], "RECYCLE": ["RX"], "RXOUT": ["SEP"]}


def test_block_edges_internal_only():
    # edges only between blocks (external feeds/products excluded)
    assert block_edges(SPEC) == {("RX", "SEP"), ("SEP", "RX")}
