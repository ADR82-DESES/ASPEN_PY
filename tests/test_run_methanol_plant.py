import sys
import os
import runpy
from unittest.mock import MagicMock, patch, PropertyMock
import pytest

def _run_script(mock_aspen, capsys):
    mock_win32_module = MagicMock()
    mock_win32_module.Dispatch.return_value = mock_aspen
    
    with patch.dict(sys.modules, {"win32com": MagicMock(), "win32com.client": mock_win32_module}):
        script_path = os.path.join(os.path.dirname(__file__), "..", "run_methanol_plant.py")
        script_path = os.path.abspath(script_path)
        
        try:
            runpy.run_path(script_path, run_name="__main__")
            exit_code = 0
        except SystemExit as exc:
            exit_code = exc.code
            
        captured = capsys.readouterr()
        return exit_code, captured.out

def test_01_no_blocks(capsys):
    mock_aspen = MagicMock()
    mock_aspen.Tree.FindNode.return_value = None  # blocks absent
    
    exit_code, stdout = _run_script(mock_aspen, capsys)
    
    assert exit_code == 1
    assert "ERROR: NO_BLOCKS" in stdout

def test_02_not_converged(capsys):
    mock_aspen = MagicMock()
    blocks_node = MagicMock()
    per_error_node = MagicMock()
    per_error_node.Value = 2
    mock_aspen.Tree.FindNode.side_effect = [blocks_node, per_error_node]
    mock_aspen.Engine.IsRunning = False
    
    exit_code, stdout = _run_script(mock_aspen, capsys)
    
    assert exit_code == 3
    assert "WARNING: NOT_CONVERGED" in stdout
    assert "WARNING: OUTPUT_NOT_SAVED" in stdout

def test_03_save_failed(capsys):
    mock_aspen = MagicMock()
    blocks_node = MagicMock()
    per_error_node = MagicMock()
    per_error_node.Value = 0
    mock_aspen.Tree.FindNode.side_effect = [blocks_node, per_error_node]
    mock_aspen.Engine.IsRunning = False
    mock_aspen.SaveAs.side_effect = OSError("disk full")
    
    exit_code, stdout = _run_script(mock_aspen, capsys)
    
    assert exit_code == 2
    assert "ERROR: OUTPUT_SAVE_FAILED" in stdout

def test_04_success(capsys):
    mock_aspen = MagicMock()
    blocks_node = MagicMock()
    per_error_node = MagicMock()
    per_error_node.Value = 0
    mock_aspen.Tree.FindNode.side_effect = [blocks_node, per_error_node]
    mock_aspen.Engine.IsRunning = False
    # mock_aspen.SaveAs uses default MagicMock (no side_effect)
    
    exit_code, stdout = _run_script(mock_aspen, capsys)
    
    assert exit_code == 0
    assert "OK: CONVERGED" in stdout
    assert "OK: OUTPUT_SAVED" in stdout
