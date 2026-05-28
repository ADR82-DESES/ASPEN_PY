from __future__ import annotations

from pathlib import Path

import pytest

from aspen_automation import generate_inp, load_spec, load_template
from aspen_automation.inp_generator import validate_inp


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = ROOT / "templates" / "methanol_plant_atr.yaml"
TEMPLATE_README_PATH = ROOT / "templates" / "README.md"
FEED_STREAMS = {"NG-FEED", "STEAM", "O2-FEED"}
EXPECTED_COMPONENTS = {"CH4", "H2O", "O2", "CO", "CO2", "H2", "CH3OH", "N2"}


@pytest.fixture
def template_spec():
    return load_spec(str(TEMPLATE_PATH))


def test_template_file_exists() -> None:
    assert TEMPLATE_PATH.is_file()


def test_template_loads_without_error(template_spec) -> None:
    assert isinstance(template_spec, dict)
    loaded = load_template("methanol_plant_atr")
    assert isinstance(loaded, dict)
    assert loaded["metadata"]["title"] == template_spec["metadata"]["title"]


def test_template_has_required_sections(template_spec) -> None:
    required = {"metadata", "components", "properties", "flowsheet", "streams", "blocks"}
    assert required.issubset(template_spec.keys())


def test_template_component_count(template_spec) -> None:
    components = template_spec["components"]
    ids = {component["id"] for component in components}
    assert len(components) == 8
    assert ids == EXPECTED_COMPONENTS


def test_template_feed_streams(template_spec) -> None:
    stream_names = {stream["name"] for stream in template_spec["streams"]}
    assert FEED_STREAMS.issubset(stream_names)


def test_template_product_stream_in_flowsheet(template_spec) -> None:
    outputs = {stream for connection in template_spec["flowsheet"] for stream in connection["outputs"]}
    assert "MEOH-PRO" in outputs


def test_template_has_targets(template_spec) -> None:
    targets = template_spec["targets"]
    assert targets["production_rate_tpd"] == 10000
    assert targets["purity"]["min_value"] == pytest.approx(0.9985)


def test_template_all_flowsheet_blocks_defined(template_spec) -> None:
    flowsheet_blocks = {connection["block"] for connection in template_spec["flowsheet"]}
    defined_blocks = {block["name"] for block in template_spec["blocks"]}
    assert flowsheet_blocks.issubset(defined_blocks)


def test_template_feed_streams_have_composition(template_spec) -> None:
    streams_by_name = {stream["name"]: stream for stream in template_spec["streams"]}
    for stream_name in FEED_STREAMS:
        composition = streams_by_name[stream_name]["composition"]
        assert sum(composition.values()) == pytest.approx(1.0, abs=1e-6)


def test_template_generates_inp_without_error(template_spec) -> None:
    inp = generate_inp(template_spec)
    assert isinstance(inp, str)
    assert "TITLE 'Methanol Plant 10k TPD'" in inp


def test_template_generated_inp_is_valid(template_spec) -> None:
    inp = generate_inp(template_spec)
    report = validate_inp(inp)
    assert report["valid"], report["errors"]


def test_template_readme_exists() -> None:
    assert TEMPLATE_README_PATH.is_file()
