from __future__ import annotations

import runpy
import sys
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "run_methanol_plant.py"


def _run_wrapper(*args: str) -> tuple[int, str]:
    with patch.object(sys, "argv", [str(SCRIPT_PATH), *args]):
        try:
            runpy.run_path(str(SCRIPT_PATH), run_name="__main__")
        except SystemExit as exc:
            code = int(exc.code or 0)
        else:
            code = 0
    return code, ""


def test_run_methanol_plant_wrapper_points_to_notebook(capsys) -> None:
    code, _ = _run_wrapper()
    output = capsys.readouterr().out

    assert code == 0
    assert "Compatibility" in output or "compatibility" in output
    assert "notebooks/process_library_runner.ipynb" in output
    assert "process_library/methanol/process.yaml" in output
    assert "archive/root_probes/run_methanol_plant_legacy.py" in output


def test_run_methanol_plant_wrapper_exposes_legacy_path(capsys) -> None:
    code, _ = _run_wrapper("--show-legacy-path")
    output = capsys.readouterr().out.strip()

    assert code == 0
    assert output == "archive\\root_probes\\run_methanol_plant_legacy.py" or output == (
        "archive/root_probes/run_methanol_plant_legacy.py"
    )


def test_run_methanol_plant_wrapper_help_is_safe(capsys) -> None:
    code, _ = _run_wrapper("--help")
    output = capsys.readouterr().out

    assert code == 0
    assert "Compatibility wrapper" in output
    assert "--show-legacy-path" in output
