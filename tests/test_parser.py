import pytest
import os
from aspen_automation.parser import load_spec, detect_format
from aspen_automation.exceptions import ParserError, ValidationError

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

def test_detect_format_yaml():
    assert detect_format("test.yaml") == "yaml"
    assert detect_format("test.yml") == "yaml"

def test_detect_format_json():
    assert detect_format("test.json") == "json"

def test_detect_format_unsupported():
    with pytest.raises(ParserError):
        detect_format("test.txt")

def test_load_valid_yaml():
    filepath = os.path.join(FIXTURES_DIR, "valid_plant.yaml")
    spec = load_spec(filepath)
    assert spec["metadata"]["title"] == "Simple Mixer Plant"

def test_load_with_validation_error():
    filepath = os.path.join(FIXTURES_DIR, "invalid_missing_section.yaml")
    with pytest.raises(ValidationError):
        load_spec(filepath, validate=True)

def test_load_without_validation():
    filepath = os.path.join(FIXTURES_DIR, "invalid_missing_section.yaml")
    spec = load_spec(filepath, validate=False) # Should not raise
    assert "metadata" in spec
    # It missing components, but we didn't validate

def test_load_nonexistent_file():
    with pytest.raises(ParserError):
        load_spec("nonexistent.yaml")
