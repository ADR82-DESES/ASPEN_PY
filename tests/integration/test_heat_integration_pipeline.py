import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from aspen_automation.heat_integration import analyze_heat_integration

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "lhhw_run"
SPEC_YAML = (
    Path(__file__).resolve().parents[2]
    / "process_library" / "methanol" / "process.yaml"
)


def _load():
    blocks_df = pd.read_csv(FIXTURE / "blocks.csv")
    streams_df = pd.read_csv(FIXTURE / "streams.csv")
    spec_dict = yaml.safe_load(SPEC_YAML.read_text(encoding="utf-8"))
    return blocks_df, streams_df, spec_dict


def test_pipeline_gross_numbers_match_run():
    blocks_df, streams_df, spec_dict = _load()
    kpi = analyze_heat_integration(blocks_df, streams_df, spec_dict)
    assert kpi is not None
    e = kpi["energy"]

    old_energy = json.loads((FIXTURE / "kpis.json").read_text())["energy_consumption_mw"]
    assert e["gross_abs_duty_mw"] == pytest.approx(old_energy, abs=1.0)
    assert e["gross_abs_duty_mw"] == pytest.approx(3641.74, abs=1.0)
    assert e["gross_heating_mw"] == pytest.approx(912.98, abs=1.0)
    assert e["gross_cooling_mw"] == pytest.approx(-2728.76, abs=1.0)


def test_pipeline_targets_are_thermodynamically_sane():
    blocks_df, streams_df, spec_dict = _load()
    kpi = analyze_heat_integration(blocks_df, streams_df, spec_dict)
    e = kpi["energy"]
    integ = e["integrated"]

    assert integ["min_hot_utility_mw"] >= 0.0
    assert integ["min_cold_utility_mw"] >= 0.0
    assert integ["max_recovery_mw"] >= 0.0
    # cannot need more hot utility than the total heating demand
    assert integ["min_hot_utility_mw"] <= e["gross_heating_mw"] + 1e-6
    # the integrated headline is far smaller in magnitude than the gross Σ|duty|
    assert abs(kpi["energy_consumption_mw"]) < e["gross_abs_duty_mw"]


def test_pipeline_reads_compressor_work_from_blocks():
    blocks_df, streams_df, spec_dict = _load()
    kpi = analyze_heat_integration(blocks_df, streams_df, spec_dict)
    # B-COMP net_work_mw in the fixture is ~0.3087 MW
    assert kpi["energy"]["steam_power"]["compressor_work_mw"] == pytest.approx(0.3087, abs=1e-3)
