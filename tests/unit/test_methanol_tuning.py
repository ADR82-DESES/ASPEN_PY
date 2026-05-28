from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from aspen_automation import (
    MethanolTuningSettings,
    build_methanol_tuning_variant_spec,
    run_methanol_tuning_campaign,
    score_methanol_tuning_metrics,
)
from aspen_automation.methanol_tuning import collect_methanol_tuning_metrics
from aspen_automation.parser import load_spec
from aspen_automation.process_library import ProcessLayout, ProcessRunResult


ROOT = Path(__file__).resolve().parents[2]
METHANOL_PROCESS_DIR = ROOT / "process_library" / "methanol"


def _load_methanol_spec() -> dict:
    return load_spec(str(METHANOL_PROCESS_DIR / "process.yaml"))


def _kinetic_pre_exponentials(spec: dict) -> list[float]:
    values: list[float] = []
    for chemistry in spec.get("chemistry") or []:
        for reaction in chemistry.get("reactions") or []:
            parameters = reaction.get("parameters") or {}
            if parameters.get("reaction_type") == "KINETIC":
                values.append(float(parameters["pre_exponential_factor"]))
    return values


def _block(spec: dict, name: str) -> dict:
    return next(block for block in spec["blocks"] if block["name"] == name)


def _stream(spec: dict, name: str) -> dict:
    return next(stream for stream in spec["streams"] if stream["name"] == name)


def test_methanol_tuning_variant_generation_does_not_mutate_base_spec() -> None:
    base = _load_methanol_spec()
    original_pre_exp = _kinetic_pre_exponentials(base)
    original_steam_flow = _stream(base, "STEAM")["mass_flow"]
    original_o2_flow = _stream(base, "O2-FEED")["mass_flow"]
    original_b_syn_params = dict(_block(base, "B-SYN")["parameters"])

    settings = MethanolTuningSettings(
        case_id="unit_case",
        stage="unit",
        pre_exponential_multiplier=100.0,
        length=16.0,
        diameter=6.0,
        purge_fraction=0.12,
        steam_factor=1.2,
        oxygen_factor=0.9,
    )
    variant = build_methanol_tuning_variant_spec(base, settings)

    assert _kinetic_pre_exponentials(variant) == pytest.approx([value * 100.0 for value in original_pre_exp])
    assert _stream(variant, "STEAM")["mass_flow"] == pytest.approx(original_steam_flow * 1.2)
    assert _stream(variant, "O2-FEED")["mass_flow"] == pytest.approx(original_o2_flow * 0.9)
    assert _block(variant, "B-SYN")["parameters"]["LENGTH"] == 16.0
    assert _block(variant, "B-SYN")["parameters"]["DIAM"] == 6.0
    assert _block(variant, "B-SYN")["parameters"]["CAT-WT"] == original_b_syn_params["CAT-WT"]

    split = _block(variant, "SPLIT")["split_fractions"]
    fractions = {item["stream"]: item["fraction"] for item in split}
    assert fractions == pytest.approx({"PURGE": 0.12, "RECYCLE": 0.88})
    assert sum(fractions.values()) == pytest.approx(1.0)

    assert _kinetic_pre_exponentials(base) == original_pre_exp
    assert _stream(base, "STEAM")["mass_flow"] == original_steam_flow
    assert _stream(base, "O2-FEED")["mass_flow"] == original_o2_flow
    assert _block(base, "B-SYN")["parameters"] == original_b_syn_params


def test_methanol_tuning_score_prefers_stop_rule_and_product_rate() -> None:
    failed = {
        "succeeded": False,
        "stop_rule_met": False,
        "product_ch3oh_tpd": 5000.0,
        "r_out_ch3oh_mole_frac": 0.05,
    }
    improved = {
        "succeeded": True,
        "stop_rule_met": False,
        "product_ch3oh_tpd": 300.0,
        "r_out_ch3oh_mole_frac": 0.008,
        "rin_stoichiometric_number": 1.8,
        "purge_methanol_loss_fraction": 0.3,
    }
    passed_low = {
        "succeeded": True,
        "stop_rule_met": True,
        "product_ch3oh_tpd": 600.0,
        "r_out_ch3oh_mole_frac": 0.02,
        "rin_stoichiometric_number": 1.9,
        "purge_methanol_loss_fraction": 0.25,
    }
    passed_high = {
        "succeeded": True,
        "stop_rule_met": True,
        "product_ch3oh_tpd": 800.0,
        "r_out_ch3oh_mole_frac": 0.015,
        "rin_stoichiometric_number": 1.7,
        "purge_methanol_loss_fraction": 0.4,
    }

    assert score_methanol_tuning_metrics(improved) > score_methanol_tuning_metrics(failed)
    assert score_methanol_tuning_metrics(passed_low) > score_methanol_tuning_metrics(improved)
    assert score_methanol_tuning_metrics(passed_high) > score_methanol_tuning_metrics(passed_low)


def test_collect_methanol_tuning_metrics_applies_stop_rule(tmp_path: Path) -> None:
    layout = ProcessLayout(
        process_root=tmp_path / "runs" / "case",
        run_dir=tmp_path / "runs" / "case" / "run_1",
        generated_inp_path=tmp_path / "runs" / "case" / "run_1" / "case_generated.inp",
        output_apw_path=tmp_path / "runs" / "case" / "run_1" / "case_output.apw",
        results_dir=tmp_path / "runs" / "case" / "run_1" / "results",
        reports_root=tmp_path / "runs" / "case" / "run_1" / "reports",
        session_dir=tmp_path / "runs" / "case" / "run_1" / "session",
    )
    layout.results_dir.mkdir(parents=True)
    (layout.results_dir / "kpis.json").write_text(
        json.dumps(
            {
                "product_stream": "MEOH-PRO",
                "product_component_tpd": 600.0,
                "product_total_tpd": 610.0,
                "purity_fraction": 0.99,
                "synthesis_loop": {
                    "outlet_ch3oh_mole_frac": 0.02,
                    "inlet_stoichiometric_number": 1.95,
                    "inlet_ch4_mole_frac": 0.03,
                    "inlet_co2_mole_frac": 0.05,
                },
            }
        ),
        encoding="utf-8",
    )
    (layout.results_dir / "build_diagnostics.json").write_text(
        json.dumps({"history_diagnostics": {"status": "converged", "input_translation_failed": False}}),
        encoding="utf-8",
    )
    (layout.results_dir / "simulation_diagnostics.json").write_text(
        json.dumps({"status": "succeeded", "results_status": "readable"}),
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {"stream_name": "R-OUT", "CH3OH_mole_frac": 0.02, "mass_flow": 1.0, "CH3OH_mass_frac": 0.0},
            {"stream_name": "MEOH-PRO", "mass_flow": 25252.5, "CH3OH_mass_frac": 0.99},
            {"stream_name": "PURGE", "mass_flow": 1000.0, "CH3OH_mass_frac": 0.01},
            {"stream_name": "RECYCLE", "CH4_mole_frac": 0.02, "CO2_mole_frac": 0.05},
        ]
    ).to_csv(layout.results_dir / "streams.csv", index=False)
    result = ProcessRunResult(
        process_name="case",
        process_dir=tmp_path / "case",
        spec_path=tmp_path / "case" / "process.yaml",
        status="succeeded",
        layout=layout,
    )

    metrics = collect_methanol_tuning_metrics(result)

    assert metrics["succeeded"] is True
    assert metrics["stop_rule_met"] is True
    assert metrics["purge_methanol_loss_fraction"] == pytest.approx(0.24 / (0.24 + 600.0))
    assert metrics["recycle_not_ch4_co2_dominated"] is True


def test_campaign_promotes_only_when_stop_rule_is_met(tmp_path: Path) -> None:
    process_dir = tmp_path / "process_library" / "methanol"
    shutil.copytree(METHANOL_PROCESS_DIR, process_dir)
    campaign_root = tmp_path / "campaign"
    run_counter = {"count": 0}

    def fake_runner(process_dir: Path, runs_root: Path, **kwargs) -> ProcessRunResult:
        run_counter["count"] += 1
        case_id = Path(process_dir).name
        run_dir = Path(runs_root) / case_id / f"run_{run_counter['count']}"
        results_dir = run_dir / "results"
        results_dir.mkdir(parents=True)
        product = 650.0 if case_id.startswith("s1_pre_x10") else 100.0
        r_out = 0.02 if case_id.startswith("s1_pre_x10") else 0.004
        (results_dir / "kpis.json").write_text(
            json.dumps(
                {
                    "product_stream": "MEOH-PRO",
                    "product_component_tpd": product,
                    "product_total_tpd": product,
                    "purity_fraction": 0.99,
                    "synthesis_loop": {
                        "outlet_ch3oh_mole_frac": r_out,
                        "inlet_stoichiometric_number": 1.9,
                        "inlet_ch4_mole_frac": 0.02,
                        "inlet_co2_mole_frac": 0.05,
                    },
                }
            ),
            encoding="utf-8",
        )
        (results_dir / "build_diagnostics.json").write_text(
            json.dumps({"history_diagnostics": {"status": "converged", "input_translation_failed": False}}),
            encoding="utf-8",
        )
        (results_dir / "simulation_diagnostics.json").write_text(
            json.dumps({"status": "succeeded", "results_status": "readable"}),
            encoding="utf-8",
        )
        pd.DataFrame(
            [
                {"stream_name": "R-OUT", "CH3OH_mole_frac": r_out},
                {"stream_name": "MEOH-PRO", "mass_flow": product * 1000 / 24, "CH3OH_mass_frac": 1.0},
                {"stream_name": "PURGE", "mass_flow": 1000.0, "CH3OH_mass_frac": 0.001},
                {"stream_name": "RECYCLE", "CH4_mole_frac": 0.02, "CO2_mole_frac": 0.05},
            ]
        ).to_csv(results_dir / "streams.csv", index=False)
        layout = ProcessLayout(
            process_root=Path(runs_root) / case_id,
            run_dir=run_dir,
            generated_inp_path=run_dir / f"{case_id}_generated.inp",
            output_apw_path=run_dir / f"{case_id}_output.apw",
            results_dir=results_dir,
            reports_root=run_dir / "reports",
            session_dir=run_dir / "session",
        )
        return ProcessRunResult(
            process_name=case_id,
            process_dir=Path(process_dir),
            spec_path=Path(process_dir) / "process.yaml",
            status="succeeded",
            layout=layout,
        )

    result = run_methanol_tuning_campaign(
        process_dir,
        tmp_path / "runs",
        campaign_root=campaign_root,
        runner=fake_runner,
        max_cases=20,
        promote=True,
    )

    assert result.promoted is True
    assert result.promoted_spec_path == process_dir / "process.yaml"
    assert result.backup_spec_path is not None and result.backup_spec_path.is_file()
    assert result.best_process_path is not None and result.best_process_path.is_file()
    assert result.summary_csv_path.is_file()
    assert result.summary_json_path.is_file()
    assert json.loads(result.summary_json_path.read_text(encoding="utf-8"))["best_case"]["stop_rule_met"] is True


def test_campaign_does_not_promote_when_stop_rule_is_not_met(tmp_path: Path) -> None:
    process_dir = tmp_path / "process_library" / "methanol"
    shutil.copytree(METHANOL_PROCESS_DIR, process_dir)
    original = (process_dir / "process.yaml").read_text(encoding="utf-8")

    def fake_runner(process_dir: Path, runs_root: Path, **kwargs) -> ProcessRunResult:
        case_id = Path(process_dir).name
        run_dir = Path(runs_root) / case_id / "run_1"
        results_dir = run_dir / "results"
        results_dir.mkdir(parents=True)
        (results_dir / "kpis.json").write_text(
            json.dumps(
                {
                    "product_stream": "MEOH-PRO",
                    "product_component_tpd": 50.0,
                    "product_total_tpd": 50.0,
                    "purity_fraction": 0.99,
                    "synthesis_loop": {
                        "outlet_ch3oh_mole_frac": 0.005,
                        "inlet_stoichiometric_number": 1.9,
                    },
                }
            ),
            encoding="utf-8",
        )
        (results_dir / "build_diagnostics.json").write_text(
            json.dumps({"history_diagnostics": {"status": "converged", "input_translation_failed": False}}),
            encoding="utf-8",
        )
        (results_dir / "simulation_diagnostics.json").write_text(
            json.dumps({"status": "succeeded", "results_status": "readable"}),
            encoding="utf-8",
        )
        pd.DataFrame(
            [
                {"stream_name": "R-OUT", "CH3OH_mole_frac": 0.005},
                {"stream_name": "MEOH-PRO", "mass_flow": 50.0 * 1000 / 24, "CH3OH_mass_frac": 1.0},
                {"stream_name": "PURGE", "mass_flow": 1000.0, "CH3OH_mass_frac": 0.001},
                {"stream_name": "RECYCLE", "CH4_mole_frac": 0.02, "CO2_mole_frac": 0.05},
            ]
        ).to_csv(results_dir / "streams.csv", index=False)
        layout = ProcessLayout(
            process_root=Path(runs_root) / case_id,
            run_dir=run_dir,
            generated_inp_path=run_dir / f"{case_id}_generated.inp",
            output_apw_path=run_dir / f"{case_id}_output.apw",
            results_dir=results_dir,
            reports_root=run_dir / "reports",
            session_dir=run_dir / "session",
        )
        return ProcessRunResult(
            process_name=case_id,
            process_dir=Path(process_dir),
            spec_path=Path(process_dir) / "process.yaml",
            status="succeeded",
            layout=layout,
        )

    result = run_methanol_tuning_campaign(
        process_dir,
        tmp_path / "runs",
        campaign_root=tmp_path / "campaign",
        runner=fake_runner,
        max_cases=20,
        promote=True,
    )

    assert result.promoted is False
    assert result.best_process_path is not None and result.best_process_path.is_file()
    assert (process_dir / "process.yaml").read_text(encoding="utf-8") == original
