import pytest
import os
import yaml
from aspen_automation.schema import validate_spec
from aspen_automation.parser import load_spec

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

def load_fixture(filename):
    filepath = os.path.join(FIXTURES_DIR, filename)
    with open(filepath, 'r') as f:
        return yaml.safe_load(f)

def test_valid_plant():
    spec = load_fixture("valid_plant.yaml")
    report = validate_spec(spec)
    assert report["valid"] is True
    assert len(report["errors"]) == 0

def test_methanol_plant_validates():
    spec = load_fixture("methanol_atr.yaml")
    report = validate_spec(spec)
    if not report["valid"]:
        print(f"\nVALIDATION ERRORS: {report['errors']}")
    assert report["valid"] is True
    assert len(report["errors"]) == 0

def test_missing_metadata():
    spec = load_fixture("valid_plant.yaml")
    del spec["metadata"]
    report = validate_spec(spec)
    assert report["valid"] is False
    assert any("Missing required top-level section 'metadata'" in e["message"] for e in report["errors"])

def test_missing_components_section():
    spec = load_fixture("invalid_missing_section.yaml")
    report = validate_spec(spec)
    assert report["valid"] is False
    assert any("Missing required top-level section 'components'" in e["message"] for e in report["errors"])

def test_invalid_units():
    spec = load_fixture("invalid_units.yaml")
    report = validate_spec(spec)
    assert report["valid"] is False
    assert any("Invalid pressure unit" in e["message"] for e in report["errors"])

def test_invalid_component_reference():
    spec = load_fixture("invalid_component_ref.yaml")
    report = validate_spec(spec)
    assert report["valid"] is False
    assert any("Undefined component 'UNKNOWN_COMP'" in e["message"] for e in report["errors"])

def test_invalid_stream_reference():
    spec = load_fixture("invalid_stream_ref.yaml")
    report = validate_spec(spec)
    assert report["valid"] is False
    assert any("Undefined input stream 'S_UNKNOWN'" in e["message"] for e in report["errors"])

def test_invalid_block_reference():
    spec = load_fixture("invalid_block_ref.yaml")
    report = validate_spec(spec)
    assert report["valid"] is False
    assert any("Undefined block 'B_UNKNOWN'" in e["message"] for e in report["errors"])

def test_invalid_composition_sum():
    spec = load_fixture("invalid_composition_sum.yaml")
    report = validate_spec(spec)
    assert report["valid"] is False
    assert any("expected 1.0" in e["message"] for e in report["errors"])

def test_missing_required_fields():
    spec = load_fixture("invalid_missing_field.yaml")
    report = validate_spec(spec)
    assert report["valid"] is False
    assert any("Missing required field 'temperature'" in e["message"] for e in report["errors"])

def test_invalid_types():
    spec = load_fixture("invalid_types.yaml")
    report = validate_spec(spec)
    assert report["valid"] is False
    assert any("Field 'temperature' must be a number" in e["message"] for e in report["errors"])

def test_empty_spec():
    report = validate_spec({})
    assert report["valid"] is False
    assert len(report["errors"]) >= 6 # Missing all 6 required sections


def test_process_defaults_model_accepts_all_fields():
    """ProcessDefaults Pydantic model must exist and accept all three fields."""
    from aspen_automation.schema import ProcessDefaults
    pd_model = ProcessDefaults(
        purity_expression="CH3OH wt% in MEOH-PRO",
        product_stream="MEOH-PRO",
        convergence_block="B-ATR",
    )
    assert pd_model.purity_expression == "CH3OH wt% in MEOH-PRO"
    assert pd_model.product_stream == "MEOH-PRO"
    assert pd_model.convergence_block == "B-ATR"


def test_process_defaults_model_accepts_partial_fields():
    """ProcessDefaults fields are all optional; partial construction must not raise."""
    from aspen_automation.schema import ProcessDefaults
    pd_model = ProcessDefaults(purity_expression="NH3 wt% in NH3-PROD")
    assert pd_model.purity_expression == "NH3 wt% in NH3-PROD"
    assert pd_model.product_stream is None
    assert pd_model.convergence_block is None


def test_plant_specification_accepts_process_defaults():
    """PlantSpecification must accept an optional process_defaults section."""
    from aspen_automation.schema import PlantSpecification
    spec_dict = load_fixture("methanol_atr.yaml")
    spec_dict["process_defaults"] = {
        "purity_expression": "CH3OH wt% in MEOH-PRO",
        "product_stream": "MEOH-PRO",
        "convergence_block": "B-ATR",
    }
    report = validate_spec(spec_dict)
    assert report["valid"] is True
    ps = PlantSpecification.model_validate(spec_dict)
    assert ps.process_defaults is not None
    assert ps.process_defaults.product_stream == "MEOH-PRO"
    assert ps.process_defaults.convergence_block == "B-ATR"
