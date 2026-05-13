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


def test_load_yaml_reads_utf8_encoded_content():
    """YAML files containing non-ASCII UTF-8 characters must load correctly.

    Without explicit encoding='utf-8', open() uses the system default which on
    some Windows locales is cp1252 or latin-1, causing UnicodeDecodeError on
    characters like accented letters or special symbols in titles/descriptions.
    """
    import tempfile
    yaml_content = """\
metadata:
  title: "Réacteur de méthanol – étude"
  units:
    pressure: "bar"
    temperature: "C"
    flow: "kg/hr"
components:
  - id: "H2O"
    name: "WATER"
properties:
  method: "IDEAL"
flowsheet:
  - block: "B1"
    inputs: ["S1"]
    outputs: ["S2"]
streams:
  - name: "S1"
    temperature: 100
    pressure: 1
    mass_flow: 1000
    composition:
      H2O: 1.0
  - name: "S2"
    temperature: 150
    pressure: 1
    mass_flow: 1000
    composition:
      H2O: 1.0
blocks:
  - name: "B1"
    type: "HEATER"
    parameters:
      TEMP: 150
      PRES: 0
"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", encoding="utf-8", delete=False
    ) as f:
        f.write(yaml_content)
        yaml_path = f.name

    try:
        spec = load_spec(yaml_path)
        assert spec["metadata"]["title"] == "Réacteur de méthanol – étude"
    finally:
        os.unlink(yaml_path)
