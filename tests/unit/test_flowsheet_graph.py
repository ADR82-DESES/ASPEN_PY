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


import pytest

from aspen_automation.flowsheet_graph import block_to_equipment, equipment_shape


@pytest.mark.parametrize("block_type,category", [
    ("MIXER", "mixer"),
    ("FSPLIT", "splitter"),
    ("RADFRAC", "column"),
    ("FLASH2", "vessel"),
    ("HEATER", "heater"),
    ("COMPR", "compressor"),
    ("PUMP", "pump"),
    ("VALVE", "valve"),
    ("RGIBBS", "reactor"),
    ("RPLUG", "reactor"),
    ("RSTOIC", "reactor"),
    ("SOMETHING-ELSE", "blackbox"),
])
def test_block_to_equipment(block_type, category):
    assert block_to_equipment(block_type) == category


@pytest.mark.parametrize("category,shape", [
    ("reactor", "cylinder"),
    ("vessel", "cylinder"),
    ("column", "cylinder"),
    ("heater", "circle"),
    ("pump", "circle"),
    ("compressor", "trapezium"),
    ("mixer", "invtriangle"),
    ("splitter", "triangle"),
    ("valve", "diamond"),
    ("blackbox", "box"),
    ("unknown-category", "box"),
])
def test_equipment_shape(category, shape):
    assert equipment_shape(category) == shape


from aspen_automation.flowsheet_graph import (
    build_flowsheet_mermaid,
    build_flowsheet_graphviz,
    build_pfd_svg,
)


def test_build_flowsheet_mermaid_here():
    m = build_flowsheet_mermaid(SPEC)
    assert m.startswith("graph LR")
    assert "RX -->|RXOUT| SEP" in m


def test_build_flowsheet_graphviz_returns_svg_or_mermaid():
    kind, content = build_flowsheet_graphviz(SPEC)
    assert kind in {"graphviz-svg", "mermaid"}
    assert content
    if kind == "graphviz-svg":
        assert "<svg" in content


def test_build_pfd_svg_source_and_content():
    source, content = build_pfd_svg(SPEC)
    assert source in {"graphviz-svg", "mermaid"}
    assert content.strip()
