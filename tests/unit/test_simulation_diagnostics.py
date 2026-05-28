from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

sys.modules.setdefault("win32com", MagicMock())
sys.modules.setdefault("win32com.client", MagicMock())

from aspen_automation.simulation_diagnostics import (
    _normalize_block_names,
    read_aspen_run_diagnostics,
)


def test_normalize_block_names_empty_input_returns_empty():
    """_normalize_block_names(None) must not inject any hardcoded block name."""
    result = _normalize_block_names(None)
    assert result == [], f"Expected [], got {result!r}"


def test_normalize_block_names_empty_list_returns_empty():
    result = _normalize_block_names([])
    assert result == [], f"Expected [], got {result!r}"


def test_normalize_block_names_preserves_explicit_names():
    result = _normalize_block_names(["B-ATR", "B-SEP"])
    assert result == ["B-ATR", "B-SEP"]


def test_normalize_block_names_deduplicates_case_insensitive():
    result = _normalize_block_names(["BLOCK1", "block1", "BLOCK2"])
    assert result == ["BLOCK1", "BLOCK2"]


def _node(value):
    n = MagicMock()
    n.Value = value
    return n


def _make_aspen(per_error=None):
    aspen = MagicMock()
    aspen.Tree.FindNode.return_value = _node(per_error)
    return aspen


def test_convergence_unknown_when_no_per_error_and_no_block_names():
    """When PER_ERROR is absent and no block_names supplied, status must be 'unknown'.

    Previously the code injected 'B-ATR' and queried it; if the mock returned
    None (block absent) the loop continued and status stayed 'unknown'. After the
    fix the loop body is simply never entered when block_names is None/empty.
    """
    aspen = MagicMock()
    aspen.Tree.FindNode.return_value = None  # all paths return None

    result = read_aspen_run_diagnostics(aspen)
    assert result["convergence_status"] == "unknown"
    assert result["status_source"] == "unresolved"


def test_batr_block_not_probed_when_block_names_omitted():
    """No query to \\Data\\Blocks\\B-ATR\\... should occur when block_names is not passed."""
    aspen = MagicMock()
    aspen.Tree.FindNode.return_value = None

    read_aspen_run_diagnostics(aspen)

    called_paths = [call.args[0] for call in aspen.Tree.FindNode.call_args_list]
    batr_paths = [p for p in called_paths if "B-ATR" in p]
    assert not batr_paths, f"B-ATR was probed unexpectedly: {batr_paths}"
