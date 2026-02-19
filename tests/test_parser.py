import pytest
import os
import yaml
import json
from aspen_automation.parser import load_spec
from aspen_automation.exceptions import ValidationError
from aspen_automation.schema import PlantSpecification

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

def test_load_valid_yaml():
    path = os.path.join(FIXTURE_DIR, "valid_plant.yaml")
    spec = load_spec(path)
    assert isinstance(spec, PlantSpecification)
    assert spec.metadata.title == "Methanol Plant 10k TPD"

def test_load_valid_json(tmp_path):
    path = os.path.join(FIXTURE_DIR, "valid_plant.yaml")
    with open(path, 'r') as f:
        data = yaml.safe_load(f)
    
    json_path = tmp_path / "plant.json"
    with open(json_path, 'w') as f:
        json.dump(data, f)
        
    spec = load_spec(str(json_path))
    assert isinstance(spec, PlantSpecification)
    assert spec.metadata.title == "Methanol Plant 10k TPD"

def test_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_spec("non_existent_file.yaml")

def test_load_invalid_raises_error():
    path = os.path.join(FIXTURE_DIR, "invalid_composition.yaml")
    with pytest.raises(ValidationError) as excinfo:
        load_spec(path)
    assert "Composition sum is 0.95" in str(excinfo.value)

def test_load_no_validate():
    path = os.path.join(FIXTURE_DIR, "invalid_composition.yaml")
    data = load_spec(path, validate=False)
    assert isinstance(data, dict)
    assert data["streams"][0]["name"] == "S1"

def test_yaml_syntax_error(tmp_path):
    p = tmp_path / "broken.yaml"
    p.write_text("invalid: [unclosed bracket")
    with pytest.raises(ValueError) as excinfo:
        load_spec(str(p))
    assert "YAML syntax error" in str(excinfo.value)

def test_json_syntax_error(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text('{"invalid": "unclosed quote}')
    with pytest.raises(ValueError) as excinfo:
        load_spec(str(p))
    assert "JSON syntax error" in str(excinfo.value)
