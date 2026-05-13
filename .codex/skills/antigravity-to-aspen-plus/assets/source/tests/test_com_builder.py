from pathlib import Path
from unittest.mock import MagicMock, patch

from aspen_automation import load_spec
from aspen_automation.com_builder import (
    _block_model_candidates,
    _order_output_nodes,
    build_flowsheet_via_com,
    infer_external_feed_streams,
)


ROOT = Path(__file__).resolve().parents[1]
METHANOL_TEMPLATE_PATH = ROOT / "templates" / "methanol_plant_atr.yaml"


class _NamedNode:
    def __init__(self, name: str) -> None:
        self.Name = name


def test_infer_external_feed_streams_from_methanol_template() -> None:
    spec = load_spec(str(METHANOL_TEMPLATE_PATH))

    assert infer_external_feed_streams(spec) == ["NG-FEED", "STEAM", "O2-FEED"]


def test_block_model_candidates_keep_common_variants() -> None:
    assert _block_model_candidates("flash2") == ["flash2", "FLASH2", "Flash2"]


def test_order_output_nodes_prefers_vapor_like_port_for_flash_gas_stream() -> None:
    ports = [_NamedNode("L(OUT)"), _NamedNode("V(OUT)")]

    ordered = _order_output_nodes("FLASH2", ["GAS-PURG", "CRUDE-ME"], ports)

    assert [node.Name for node in ordered] == ["V(OUT)", "L(OUT)"]


def test_build_flowsheet_via_com_orchestrates_builder_steps() -> None:
    spec = load_spec(str(METHANOL_TEMPLATE_PATH))
    fake_aspen = MagicMock(name="aspen")

    with (
        patch("aspen_automation.com_builder._set_property_method") as mock_property,
        patch("aspen_automation.com_builder._ensure_components") as mock_components,
        patch("aspen_automation.com_builder._ensure_streams") as mock_streams,
        patch("aspen_automation.com_builder._ensure_blocks", return_value=MagicMock(name="strategy", name_attr="elements_add", type_field="")) as mock_blocks,
        patch("aspen_automation.com_builder._connect_flowsheet") as mock_connect,
        patch("aspen_automation.com_builder._configure_feed_streams") as mock_feeds,
        patch("aspen_automation.com_builder._apply_block_configuration") as mock_config,
        patch(
            "aspen_automation.com_builder._verify_materialized_flowsheet",
            return_value={
                "build_valid": True,
                "stream_count": 3,
                "block_count": 2,
                "stream_samples": ["NG-FEED", "STEAM", "O2-FEED"],
                "block_samples": ["MIX-FEED", "B-ATR"],
            },
        ) as mock_verify,
    ):
        strategy = mock_blocks.return_value
        strategy.name = "elements_add"
        strategy.type_field = ""
        diagnostics = build_flowsheet_via_com(spec, fake_aspen)

    assert diagnostics["build_mechanism"] == "com_block_builder"
    assert diagnostics["feed_streams"] == ["NG-FEED", "STEAM", "O2-FEED"]
    assert diagnostics["build_valid"] is True
    mock_property.assert_called_once()
    mock_components.assert_called_once()
    mock_streams.assert_called_once()
    mock_blocks.assert_called_once()
    mock_connect.assert_called_once()
    mock_feeds.assert_called_once()
    mock_config.assert_called_once()
    mock_verify.assert_called_once()
