import os
import yaml
import json
from typing import Dict, Any, Union
from .schema import PlantSpecification
from .validator import validate_spec
from .exceptions import ValidationError

def load_spec(filepath: str, validate: bool = True) -> Union[PlantSpecification, Dict[str, Any]]:
    """
    Load a plant specification from a YAML or JSON file.
    
    Args:
        filepath: Path to the input file (.yaml, .yml, or .json)
        validate: Whether to perform comprehensive validation (default: True)
        
    Returns:
        PlantSpecification object if validated, otherwise raw dict
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValidationError: If validation fails
        yaml.YAMLError: If YAML syntax is invalid
        json.JSONDecodeError: If JSON syntax is invalid
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    _, ext = os.path.splitext(filepath)
    ext = ext.lower()

    try:
        with open(filepath, 'r') as f:
            if ext in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            elif ext == '.json':
                data = json.load(f)
            else:
                raise ValueError(f"Unsupported file extension: {ext}. Use .yaml, .yml, or .json")
    except yaml.YAMLError as e:
        # Prepend helpful context to the YAML error message
        raise ValueError(f"YAML syntax error: {str(e)}") from e
    except json.JSONDecodeError as e:
        # JSON syntax error with clear coordinates as requested
        msg = f"JSON syntax error at line {e.lineno}, col {e.colno}: {e.msg}"
        raise ValueError(msg) from e

    if validate:
        report = validate_spec(data)
        if not report["valid"]:
            raise ValidationError(report)
        return PlantSpecification(**data)
    
    return data
