import sys
from unittest.mock import MagicMock

# Mock win32com before any imports
sys.modules["win32com"] = MagicMock()
sys.modules["win32com.client"] = MagicMock()

import datetime
import json
import os

import pandas as pd
import pytest

from aspen_automation.reporter import (
    _create_run_dir,
    _print_console_summary,
    _write_csv_reports,
    _write_html_summary,
    _write_json_reports,
    _write_markdown_summary,
    generate_reports,
)


def _make_results():
    return {
        "streams": pd.DataFrame(
            [
                {
                    "stream_name": "S1",
                    "temperature": 25.0,
                    "pressure": 1.0,
                    "mass_flow": 100.0,
                    "mole_flow": 50.0,
                }
            ]
        ),
        "blocks": pd.DataFrame(
            [
                {
                    "block_name": "B1",
                    "block_type": "R",
                    "duty": 10.0,
                    "conversion": 0.9,
                    "efficiency": 0.8,
                }
            ]
        ),
        "material_balance": pd.DataFrame(
            [{"component": "CH3OH", "input_kmol_hr": 10.0, "output_kmol_hr": 9.9, "closure_%": -1.0}]
        ),
        "energy_balance": pd.DataFrame(
            [{"block_name": "B1", "duty_kw": 1000.0}, {"block_name": "TOTAL", "duty_kw": 1000.0}]
        ),
        "kpis": {
            "production_rate_tpd": 2.4,
            "purity_fraction": 0.99,
            "energy_consumption_mw": 1.0,
            "yield_fraction": 0.8,
            "convergence_status": "converged",
        },
        "diagnostics": {"per_error": 0, "error_count": 0, "warning_count": 0, "convergence_status": "converged"},
        "metadata": {"extracted_at": datetime.datetime.now().isoformat(), "stream_count": 1, "block_count": 1},
    }


@pytest.fixture
def spec():
    return {"metadata": {"title": "Test"}}


def test_create_run_dir_format(tmp_path):
    path = _create_run_dir(str(tmp_path))
    assert os.path.basename(path).startswith("run_")


def test_create_run_dir_exists(tmp_path):
    path = _create_run_dir(str(tmp_path))
    assert os.path.isdir(path)


def test_write_csv_streams(tmp_path):
    run_dir = _create_run_dir(str(tmp_path))
    _write_csv_reports(_make_results(), run_dir)
    assert os.path.exists(os.path.join(run_dir, "streams.csv"))


def test_write_csv_blocks(tmp_path):
    run_dir = _create_run_dir(str(tmp_path))
    _write_csv_reports(_make_results(), run_dir)
    assert os.path.exists(os.path.join(run_dir, "blocks.csv"))


def test_write_csv_balances(tmp_path):
    run_dir = _create_run_dir(str(tmp_path))
    _write_csv_reports(_make_results(), run_dir)
    assert os.path.exists(os.path.join(run_dir, "material_balance.csv"))
    assert os.path.exists(os.path.join(run_dir, "energy_balance.csv"))


def test_write_json_kpis(tmp_path):
    run_dir = _create_run_dir(str(tmp_path))
    _write_json_reports(_make_results(), run_dir)
    with open(os.path.join(run_dir, "kpis.json"), "r", encoding="utf-8") as f:
        json.loads(f.read())


def test_write_json_diagnostics(tmp_path):
    run_dir = _create_run_dir(str(tmp_path))
    _write_json_reports(_make_results(), run_dir)
    with open(os.path.join(run_dir, "diagnostics.json"), "r", encoding="utf-8") as f:
        json.loads(f.read())


def test_write_html_summary(tmp_path, spec):
    run_dir = _create_run_dir(str(tmp_path))
    _write_html_summary(_make_results(), spec, run_dir)
    summary_path = os.path.join(run_dir, "run_summary.html")
    assert os.path.exists(summary_path)
    with open(summary_path, "r", encoding="utf-8") as f:
        content = f.read().lower()
    assert "<html" in content


def test_write_markdown_summary(tmp_path, spec):
    run_dir = generate_reports(_make_results(), spec, output_dir=str(tmp_path), format="markdown")
    assert os.path.exists(os.path.join(run_dir, "run_summary.md"))


def test_console_summary_output(tmp_path, capsys):
    run_dir = _create_run_dir(str(tmp_path))
    _write_csv_reports(_make_results(), run_dir)
    _write_json_reports(_make_results(), run_dir)
    _print_console_summary(_make_results(), run_dir)
    captured = capsys.readouterr()
    assert "converged" in captured.out


def test_generate_reports_returns_path(tmp_path, spec):
    run_dir = generate_reports(_make_results(), spec, output_dir=str(tmp_path), format="html")
    assert os.path.exists(run_dir)


def test_generate_reports_all_files(tmp_path, spec):
    run_dir = generate_reports(_make_results(), spec, output_dir=str(tmp_path), format="html")
    expected_files = {
        "streams.csv",
        "blocks.csv",
        "material_balance.csv",
        "energy_balance.csv",
        "kpis.json",
        "diagnostics.json",
        "run_summary.html",
    }
    assert expected_files.issubset(set(os.listdir(run_dir)))
