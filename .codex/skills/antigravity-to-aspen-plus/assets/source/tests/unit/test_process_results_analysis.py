from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from aspen_automation.process_results_analysis import (
    build_codex_results_markdown,
    load_result_artifact_tables,
    resolve_result_artifact_paths,
)


def _write_csv(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def test_load_result_artifact_tables_prefers_report_dir(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "run_1"
    results_dir = tmp_path / "results"

    _write_csv(report_dir / "streams.csv", pd.DataFrame([{"stream_name": "REPORT"}]))
    _write_csv(report_dir / "blocks.csv", pd.DataFrame([{"block_name": "REPORT-BLOCK"}]))
    _write_csv(report_dir / "material_balance.csv", pd.DataFrame([{"component": "CH4"}]))
    _write_csv(report_dir / "energy_balance.csv", pd.DataFrame([{"block_name": "TOTAL", "duty_mw": 1.0}]))
    _write_csv(results_dir / "streams.csv", pd.DataFrame([{"stream_name": "RESULTS"}]))

    result = SimpleNamespace(
        report_dir=report_dir,
        layout=SimpleNamespace(results_dir=results_dir),
    )

    artifact_paths, tables = load_result_artifact_tables(result)

    assert resolve_result_artifact_paths(result)["streams"] == report_dir / "streams.csv"
    assert tables["streams"].iloc[0]["stream_name"] == "REPORT"
    assert set(artifact_paths) == {"streams", "blocks", "material_balance", "energy_balance"}


def test_build_codex_results_markdown_uses_csv_observations(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "run_1"
    _write_csv(
        report_dir / "streams.csv",
        pd.DataFrame(
            [
                {"stream_name": "NG-FEED", "mass_flow": 220000.0, "CH3OH_mass_frac": 0.0},
                {
                    "stream_name": "R-IN",
                    "mass_flow": 6855814.32,
                    "mole_flow": 300468.88,
                    "CH4_mole_frac": 0.61,
                    "CO_mole_frac": 0.035,
                    "CO2_mole_frac": 0.268,
                    "H2_mole_frac": 0.083,
                    "CH3OH_mole_frac": 0.0,
                    "CH3OH_mass_frac": 0.0,
                },
                {
                    "stream_name": "R-OUT",
                    "mass_flow": 6855814.32,
                    "mole_flow": 282764.154,
                    "CH4_mole_frac": 0.679,
                    "CO_mole_frac": 0.00005,
                    "CO2_mole_frac": 0.290,
                    "H2_mole_frac": 0.00033,
                    "CH3OH_mole_frac": 0.0,
                    "CH3OH_mass_frac": 0.0,
                },
                {"stream_name": "CRUDE-MEOH", "mass_flow": 15000.0, "CH3OH_mass_frac": 0.82},
                {"stream_name": "MEOH-PRO", "mass_flow": 130.0, "CH3OH_mass_frac": 0.000002},
            ]
        ),
    )
    _write_csv(
        report_dir / "blocks.csv",
        pd.DataFrame(
            [
                {"block_name": "B-SEP", "duty_mw": -210.0},
                {"block_name": "B-SYN", "duty_mw": 45.0},
            ]
        ),
    )
    _write_csv(
        report_dir / "material_balance.csv",
        pd.DataFrame(
            [
                {"component": "CH4", "closure_pct": -2.5},
                {"component": "H2O", "closure_pct": 0.5},
            ]
        ),
    )
    _write_csv(
        report_dir / "energy_balance.csv",
        pd.DataFrame(
            [
                {"block_name": "B-SEP", "duty_mw": -210.0},
                {"block_name": "B-SYN", "duty_mw": 45.0},
                {"block_name": "TOTAL", "duty_mw": -165.0},
            ]
        ),
    )

    result = SimpleNamespace(report_dir=report_dir, layout=SimpleNamespace(results_dir=tmp_path / "results"))
    artifact_paths, tables = load_result_artifact_tables(result)

    markdown = build_codex_results_markdown(
        "methanol",
        artifact_paths,
        tables,
        acceptance={"passed": False},
    )

    assert "Codex Session Analysis: `methanol`" in markdown
    assert "`streams.csv`" in markdown
    assert "CRUDE-MEOH" in markdown
    assert "B-SYN selectivity diagnostics" in markdown
    assert "Recycle feed diagnostics" in markdown
    assert "Product-stream warning" in markdown
    assert "Largest absolute block duties" in markdown
    assert "Largest feed/product closure gaps" in markdown
    assert "Acceptance status from `acceptance.json`: False." in markdown
