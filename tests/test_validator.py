import pytest
import os
import yaml
from aspen_automation.validator import validate_spec

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

def load_fixture(name):
    path = os.path.join(FIXTURE_DIR, name)
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def test_rule1_missing_sections():
    data = {"metadata": {"title": "X", "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}}}
    # Missing components, properties, etc.
    report = validate_spec(data)
    assert not report["valid"]
    # Pydantic will catch missing fields in PlantSpecification
    errors = [e["location"] for e in report["errors"]]
    assert "components" in errors
    assert "properties" in errors

def test_rule2_invalid_component_ref():
    data = load_fixture("invalid_references.yaml")
    report = validate_spec(data)
    assert not report["valid"]
    error_msgs = [e["message"] for e in report["errors"]]
    assert any("Component 'UNDEFINED_COMP' used but not defined" in m for m in error_msgs)

def test_rule3_invalid_stream_connectivity():
    data = load_fixture("invalid_references.yaml")
    report = validate_spec(data)
    assert not report["valid"]
    error_msgs = [e["message"] for e in report["errors"]]
    assert any("Undefined input stream" in m for m in error_msgs)

def test_rule4_composition_sum():
    data = load_fixture("invalid_composition.yaml")
    report = validate_spec(data)
    assert not report["valid"]
    assert any("Composition sum is 0.95" in e["message"] for e in report["errors"])

def test_rule5_invalid_block_ref():
    data = load_fixture("invalid_references.yaml")
    report = validate_spec(data)
    assert not report["valid"]
    error_msgs = [e["message"] for e in report["errors"]]
    assert any("Block 'UNDEFINED-BLOCK' referenced but not defined" in m for m in error_msgs)

def test_rule6_invalid_units():
    data = load_fixture("invalid_units.yaml")
    report = validate_spec(data)
    assert not report["valid"]
    locations = [e["location"] for e in report["errors"]]
    assert "metadata.units.pressure" in locations
    assert "metadata.units.temperature" in locations
    assert "metadata.units.flow" in locations

def test_rule7_missing_required_fields():
    data = load_fixture("invalid_missing_fields.yaml")
    report = validate_spec(data)
    assert not report["valid"]
    locations = [e["location"] for e in report["errors"]]
    assert "streams.0.temperature" in locations
    assert "streams.0.pressure" in locations

def test_rule8_type_validation():
    data = load_fixture("invalid_types.yaml")
    report = validate_spec(data)
    assert not report["valid"]
    locations = [e["location"] for e in report["errors"]]
    assert "streams.0.temperature" in locations

def test_valid_spec_passes_all():
    data = load_fixture("valid_plant.yaml")
    report = validate_spec(data)
    assert report["valid"]
    assert len(report["errors"]) == 0

def test_chemistry_invalid_component_ref():
    data = load_fixture("invalid_chemistry.yaml")
    report = validate_spec(data)
    assert not report["valid"]
    # Check that the location path includes .stoichiometry
    locations = [e["location"] for e in report["errors"]]
    assert "chemistry[0].reactions[0].stoichiometry[0]" in locations
    
    error_msgs = [e["message"] for e in report["errors"]]
    assert any("Component 'UNDEFINED_COMP' used in reaction but not defined" in m for m in error_msgs)

def test_rule9_duplicate_names():
    data = load_fixture("duplicate_names.yaml")
    report = validate_spec(data)
    assert not report["valid"]
    
    locations = [e["location"] for e in report["errors"]]
    assert "components[1]" in locations
    assert "streams[1]" in locations
    assert "blocks[1]" in locations
    
    error_msgs = [e["message"] for e in report["errors"]]
    assert any("Duplicate component ID 'CH4' found" in m for m in error_msgs)
    assert any("Duplicate stream name 'S1' found" in m for m in error_msgs)
    assert any("Duplicate block name 'B1' found" in m for m in error_msgs)

def test_unknown_fields_validation():
    data = load_fixture("unknown_fields.yaml")
    report = validate_spec(data)
    assert not report["valid"]
    
    locations = [e["location"] for e in report["errors"]]
    # We expect errors for both 'metadata.unknown_metadata_field' and 'unknown_root_field'
    assert "metadata.unknown_metadata_field" in locations
    assert "unknown_root_field" in locations
    
    for error in report["errors"]:
        if error["location"] in ["metadata.unknown_metadata_field", "unknown_root_field"]:
            assert "Extra inputs are not permitted" in error["message"]

