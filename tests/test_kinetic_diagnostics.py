from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from aspen_automation import (
    build_reactor_only_kinetic_sweep_specs,
    diagnose_kinetic_sweep_results,
    generate_inp,
    load_spec,
)


ROOT = Path(__file__).resolve().parents[1]
METHANOL_PROCESS_YAML = ROOT / "process_library" / "methanol" / "process.yaml"


def _kinetic_parameters(spec):
    return [
        reaction["parameters"]
        for section in spec["chemistry"]
        for reaction in section["reactions"]
        if reaction["parameters"]["reaction_type"] == "KINETIC"
    ]


def test_reactor_only_sweep_specs_isolate_b_syn_and_keep_r_in_fixed() -> None:
    source_spec = load_spec(str(METHANOL_PROCESS_YAML))
    source_r_in = next(stream for stream in source_spec["streams"] if stream["name"] == "R-IN")

    cases = build_reactor_only_kinetic_sweep_specs(source_spec)

    assert cases
    for case in cases:
        case_data = case.spec.model_dump(mode="json")
        assert case_data["flowsheet"] == [{"block": "B-SYN", "inputs": ["R-IN"], "outputs": ["R-OUT"]}]
        assert [block["name"] for block in case_data["blocks"]] == ["B-SYN"]
        assert {stream["name"] for stream in case_data["streams"]} == {"R-IN", "R-OUT"}
        assert "RECYCLE" not in {stream["name"] for stream in case_data["streams"]}
        assert "PURGE" not in {stream["name"] for stream in case_data["streams"]}
        assert "B-ATR" not in {block["name"] for block in case_data["blocks"]}
        assert "B-DIST" not in {block["name"] for block in case_data["blocks"]}
        assert "MIX-LOOP" not in {block["name"] for block in case_data["blocks"]}

        case_r_in = next(stream for stream in case_data["streams"] if stream["name"] == "R-IN")
        assert case_r_in["composition"] == source_r_in["composition"]
        assert case_r_in["pressure"] == source_r_in["pressure"]
        assert case_r_in["temperature"] == source_r_in["temperature"]
        assert case_r_in["mass_flow"] == source_r_in["mass_flow"]
        assert case_r_in["mole_flow"] == source_r_in["mole_flow"]

        inp = generate_inp(case.spec)
        assert "BLOCK B-SYN RPLUG" in inp
        assert "REACTIONS RXN-SET1 POWERLAW" in inp
        assert "BLOCK B-ATR" not in inp
        assert "BLOCK B-DIST" not in inp
        assert "BLOCK MIX-LOOP" not in inp
        assert "RECYCLE" not in inp
        assert "PURGE" not in inp


def test_reactor_only_sweep_scales_kinetics_without_mutating_source_spec() -> None:
    source_spec = load_spec(str(METHANOL_PROCESS_YAML))
    original_pre_exp = [params["pre_exponential_factor"] for params in _kinetic_parameters(source_spec)]
    original_activation = [params["activation_energy"] for params in _kinetic_parameters(source_spec)]

    cases = build_reactor_only_kinetic_sweep_specs(source_spec)
    assert len(cases) == 8
    assert {case.pre_exponential_multiplier for case in cases} == {1.0, 1e3, 1e6, 1e9}
    assert {case.activation_energy_override for case in cases} == {None, 0.0}

    for case in cases:
        case_params = _kinetic_parameters(case.spec.model_dump(mode="json"))
        assert [params["pre_exponential_factor"] for params in case_params] == pytest.approx(
            [value * case.pre_exponential_multiplier for value in original_pre_exp]
        )
        if case.activation_energy_override is None:
            assert [params["activation_energy"] for params in case_params] == original_activation
        else:
            assert [params["activation_energy"] for params in case_params] == [0.0, 0.0, 0.0]

    assert [params["pre_exponential_factor"] for params in _kinetic_parameters(source_spec)] == original_pre_exp
    assert [params["activation_energy"] for params in _kinetic_parameters(source_spec)] == original_activation


def test_diagnose_kinetic_sweep_results_flags_kinetic_scaling_when_methanol_appears() -> None:
    case_results = [
        {
            "label": "preexp_x1_original_E",
            "pre_exponential_multiplier": 1.0,
            "activation_energy_override": None,
            "streams": pd.DataFrame(
                [
                    {"stream_name": "R-IN", "CH3OH_mole_frac": 2.0e-8},
                    {"stream_name": "R-OUT", "CH3OH_mole_frac": 2.0e-8},
                ]
            ),
        },
        {
            "label": "preexp_x1e9_E_0",
            "pre_exponential_multiplier": 1e9,
            "activation_energy_override": 0.0,
            "streams": pd.DataFrame(
                [
                    {"stream_name": "R-IN", "CH3OH_mole_frac": 2.0e-8},
                    {"stream_name": "R-OUT", "CH3OH_mole_frac": 5.0e-5},
                ]
            ),
        },
    ]

    diagnosis = diagnose_kinetic_sweep_results(case_results)

    assert diagnosis["diagnosis"] == "kinetic_scaling_or_units"
    assert diagnosis["methanol_appeared"] is True
    assert diagnosis["triggering_case_label"] == "preexp_x1e9_E_0"
    assert diagnosis["rows"][1]["delta_ch3oh_mole_frac"] == pytest.approx(4.998e-5)


def test_diagnose_kinetic_sweep_results_flags_powerlaw_spec_when_methanol_stays_absent() -> None:
    case_results = [
        {
            "label": "preexp_x1_original_E",
            "pre_exponential_multiplier": 1.0,
            "activation_energy_override": None,
            "streams": [
                {"stream_name": "R-IN", "CH3OH_mole_frac": 2.0e-8},
                {"stream_name": "R-OUT", "CH3OH_mole_frac": 2.0e-8},
            ],
        },
        {
            "label": "preexp_x1e9_E_0",
            "pre_exponential_multiplier": 1e9,
            "activation_energy_override": 0.0,
            "streams": {
                "R-IN": {"CH3OH_mole_frac": 2.0e-8},
                "R-OUT": {"CH3OH_mole_frac": 2.5e-8},
            },
        },
    ]

    diagnosis = diagnose_kinetic_sweep_results(case_results)

    assert diagnosis["diagnosis"] == "powerlaw_rplug_specification"
    assert diagnosis["methanol_appeared"] is False
    assert diagnosis["triggering_case_label"] is None
    assert all(not row["methanol_appeared"] for row in diagnosis["rows"])
