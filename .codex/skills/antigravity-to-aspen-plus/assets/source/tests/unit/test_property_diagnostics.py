from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from aspen_automation import load_spec
from aspen_automation.property_diagnostics import (
    assess_nrtl_binary_parameters,
    extract_model_quality_warnings,
)
from aspen_automation.serialization import spec_to_plain_dict

ROOT = Path(__file__).resolve().parents[2]
METHANOL_PROCESS_PATH = ROOT / "process_library" / "methanol" / "process.yaml"


def test_nrtl_binary_parameter_status_accepts_clean_aspen_history():
    spec = spec_to_plain_dict(load_spec(str(METHANOL_PROCESS_PATH)))
    history = {"status": "converged", "messages": []}

    status = assess_nrtl_binary_parameters(spec, history)

    assert status["status"] == "accepted_by_aspen"
    assert status["required_pairs"] == [["CH3OH", "H2O"]]
    assert status["provided_pairs"] == [["CH3OH", "H2O"]]
    assert status["missing_pairs"] == []
    assert status["zero_parameter_warning_present"] is False


def test_nrtl_binary_parameter_status_flags_aspen_zero_parameter_warning():
    spec = spec_to_plain_dict(load_spec(str(METHANOL_PROCESS_PATH)))
    history = {
        "status": "converged",
        "messages": [
            {
                "severity": "warning",
                "message": "NRTL BINARY PARAMETERS FOR ALL COMPONENT PAIRS ARE ZERO.",
            }
        ],
    }

    status = assess_nrtl_binary_parameters(spec, history)
    warnings = extract_model_quality_warnings(history)

    assert status["status"] == "warning_from_aspen"
    assert status["zero_parameter_warning_present"] is True
    assert warnings == ["NRTL BINARY PARAMETERS FOR ALL COMPONENT PAIRS ARE ZERO."]


def test_nrtl_binary_parameter_status_reports_missing_required_pair():
    spec = spec_to_plain_dict(load_spec(str(METHANOL_PROCESS_PATH)))
    missing = deepcopy(spec)
    missing["properties"].pop("binary_parameters", None)

    status = assess_nrtl_binary_parameters(missing)

    assert status["status"] == "missing"
    assert status["missing_pairs"] == [["CH3OH", "H2O"]]
