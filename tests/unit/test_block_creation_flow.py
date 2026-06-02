import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aspen_automation import generate_inp, load_spec
from aspen_automation.exceptions import BuildError

try:
    from aspen_automation.session import _verify_flowsheet
except ModuleNotFoundError as exc:
    if exc.name not in {"win32com", "win32com.client"}:
        raise
    with patch.dict(
        sys.modules,
        {"win32com": MagicMock(), "win32com.client": MagicMock()},
    ):
        from aspen_automation.session import _verify_flowsheet

YAML_PATH = Path(__file__).resolve().parents[2] / "templates" / "methanol_plant_atr.yaml"


def test_generate_inp_contains_all_10_blocks(tmp_path):
    spec = load_spec(str(YAML_PATH))
    generate_inp(spec, output_path=str(tmp_path / "test.inp"))
    content = (tmp_path / "test.inp").read_text()

    assert "BLOCK MIX-FEED MIXER" in content
    assert "BLOCK B-ATR RGIBBS" in content
    assert "BLOCK B-COOL HEATER" in content
    assert "BLOCK B-FLASH FLASH2" in content
    assert "BLOCK B-COMP COMPR" in content
    assert "BLOCK MIX-LOOP MIXER" in content
    assert "BLOCK B-SYN REQUIL" in content
    assert "BLOCK B-SEP FLASH2" in content
    assert "BLOCK SPLIT FSPLIT" in content
    assert "BLOCK B-DIST SEP" in content


def test_generate_inp_contains_flowsheet_section(tmp_path):
    spec = load_spec(str(YAML_PATH))
    generate_inp(spec, output_path=str(tmp_path / "test.inp"))
    content = (tmp_path / "test.inp").read_text()

    assert "FLOWSHEET" in content
    assert "BLOCK MIX-FEED IN=" in content
    assert "BLOCK B-ATR IN=" in content
    assert "BLOCK B-COOL IN=" in content
    assert "BLOCK B-FLASH IN=" in content
    assert "BLOCK B-COMP IN=" in content
    assert "BLOCK MIX-LOOP IN=" in content
    assert "BLOCK B-SYN IN=" in content
    assert "BLOCK B-SEP IN=" in content
    assert "BLOCK SPLIT IN=" in content
    assert "BLOCK B-DIST IN=" in content


def test_verify_flowsheet_raises_when_blocks_node_missing():
    mock_aspen = MagicMock()

    def side_effect(path):
        if path == r"\Data\Streams":
            return MagicMock()
        return None

    mock_aspen.Tree.FindNode.side_effect = side_effect

    with pytest.raises(BuildError) as exc_info:
        _verify_flowsheet(mock_aspen)

    assert "blocks" in str(exc_info.value).lower()


def test_verify_flowsheet_passes_when_both_nodes_present():
    mock_aspen = MagicMock()
    mock_aspen.Tree.FindNode.return_value = MagicMock()

    _verify_flowsheet(mock_aspen)

    assert mock_aspen.Tree.FindNode.call_count == 2
