import os
import json
import yaml
from typing import Dict, Any
from .exceptions import ParserError, ValidationError
from .validator import validate_spec

def detect_format(filepath: str) -> str:
    """Detect file format from extension."""
    _, ext = os.path.splitext(filepath)
    ext = ext.lower()
    if ext in ['.yaml', '.yml']:
        return 'yaml'
    elif ext == '.json':
        return 'json'
    else:
        raise ParserError(f"Unsupported file extension '{ext}'. Supported formats: .yaml, .yml, .json")

def load_yaml(filepath: str) -> Dict[str, Any]:
    """Load YAML file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ParserError(f"YAML parsing error in {filepath}: {str(e)}") from e
    except Exception as e:
        raise ParserError(f"Error reading file {filepath}: {str(e)}") from e

def load_json(filepath: str) -> Dict[str, Any]:
    """Load JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ParserError(f"JSON parsing error in {filepath} at line {e.lineno}: {e.msg}") from e
    except Exception as e:
        raise ParserError(f"Error reading file {filepath}: {str(e)}") from e

def load_spec(filepath: str, validate: bool = True) -> Dict[str, Any]:
    """
    Load specification from file and optionally validate it.

    Args:
        filepath: Path to the specification file (.yaml/.json)
        validate: Whether to run schema validation (default: True)

    Returns:
        dict: Parsed specification

    Raises:
        ParserError: If parsing fails
        ValidationError: If validation fails
    """
    fmt = detect_format(filepath)

    if fmt == 'yaml':
        spec = load_yaml(filepath)
    else:
        spec = load_json(filepath)

    if validate:
        report = validate_spec(spec)
        if not report["valid"]:
            # Construct a summary message
            msg = f"Validation failed with {len(report['errors'])} errors."
            raise ValidationError(msg, report)

    return spec
