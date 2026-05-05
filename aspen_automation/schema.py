from typing import Any, Dict, List, Optional, Union
import math
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
import enum

# Constants
VALID_PRESSURE_UNITS = ["bar", "psi", "atm", "kPa", "MPa"]
VALID_TEMPERATURE_UNITS = ["C", "F", "K", "R"]
VALID_FLOW_UNITS = ["kg/hr", "kmol/hr", "lb/hr", "lbmol/hr"]
VALID_PROPERTY_METHODS = ["RK-SOAVE", "IDEAL", "NRTL", "UNIQUAC", "PENG-ROB", "SRK"]
VALID_BLOCK_TYPES = ["MIXER", "RGIBBS", "HEATER", "FLASH2", "COMPR", "REQUIL", "FSPLIT", "SEP", "RADFRAC"]
COMPOSITION_TOLERANCE = 0.001

def create_error(message: str, location: str, suggestion: Optional[str] = None, severity: str = "error") -> Dict[str, Any]:
    """Helper to create a structured error dictionary."""
    error = {
        "severity": severity,
        "location": location,
        "message": message
    }
    if suggestion:
        error["suggestion"] = suggestion
    return error

def validate_types(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate data types of fields."""
    errors = []
    
    # Check top-level sections are of correct type (mostly covered by structure validation, but good to be explicit for contents)
    # We will check specific fields within sections
    
    # Streams
    if "streams" in spec and isinstance(spec["streams"], list):
        for i, stream in enumerate(spec["streams"]):
            if not isinstance(stream, dict):
                errors.append(create_error(f"Stream at index {i} must be a dictionary", f"streams[{i}]", "Ensure stream is defined as a dictionary"))
                continue
                
            loc = f"streams[{i}].{stream.get('name', 'unnamed')}"
            
            # Numeric fields
            for field in ["temperature", "pressure", "mass_flow", "mole_flow"]:
                if field in stream and not isinstance(stream[field], (int, float)):
                    errors.append(create_error(f"Field '{field}' must be a number", f"{loc}.{field}", f"Change value '{stream[field]}' to a number", severity="error"))
            
            # String fields
            if "name" in stream and not isinstance(stream["name"], str):
                 errors.append(create_error("Field 'name' must be a string", f"{loc}.name", "Ensure name is a string"))

            # Dict fields
            if "composition" in stream and not isinstance(stream["composition"], dict):
                errors.append(create_error("Field 'composition' must be a dictionary", f"{loc}.composition", "Define composition as a dictionary of component: value"))

    # Blocks
    if "blocks" in spec and isinstance(spec["blocks"], list):
        for i, block in enumerate(spec["blocks"]):
            if not isinstance(block, dict):
                 errors.append(create_error(f"Block at index {i} must be a dictionary", f"blocks[{i}]", "Ensure block is defined as a dictionary"))
                 continue
            
            loc = f"blocks[{i}].{block.get('name', 'unnamed')}"
            
            if "name" in block and not isinstance(block["name"], str):
                 errors.append(create_error("Field 'name' must be a string", f"{loc}.name", "Ensure name is a string"))
            if "type" in block and not isinstance(block["type"], str):
                 errors.append(create_error("Field 'type' must be a string", f"{loc}.type", "Ensure type is a string"))

    # Flowsheet
    if "flowsheet" in spec and isinstance(spec["flowsheet"], list):
        for i, entry in enumerate(spec["flowsheet"]):
            if not isinstance(entry, dict):
                errors.append(create_error(f"Flowsheet entry at index {i} must be a dictionary", f"flowsheet[{i}]", "Ensure flowsheet entry is a dictionary"))
                continue
            
            # Check lists
            for field in ["inputs", "outputs"]:
                if field in entry and not isinstance(entry[field], list):
                     errors.append(create_error(f"Field '{field}' must be a list", f"flowsheet[{i}].{field}", f"Define {field} as a list of strings"))

    # Components
    if "components" in spec and isinstance(spec["components"], list):
         for i, comp in enumerate(spec["components"]):
             if not isinstance(comp, dict):
                  errors.append(create_error(f"Component at index {i} must be a dictionary", f"components[{i}]", "Ensure component is defined as a dictionary"))

    return errors

def validate_required_fields(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate presence of required fields."""
    errors = []
    
    # Components
    if "components" in spec and isinstance(spec["components"], list):
        for i, comp in enumerate(spec["components"]):
            if isinstance(comp, dict):
                if "id" not in comp:
                    errors.append(create_error("Missing required field 'id'", f"components[{i}]", "Add 'id' field"))
                if "name" not in comp:
                     errors.append(create_error("Missing required field 'name'", f"components[{i}]", "Add 'name' field"))

    # Streams
    if "streams" in spec and isinstance(spec["streams"], list):
        for i, stream in enumerate(spec["streams"]):
            if isinstance(stream, dict):
                loc = f"streams[{i}]"
                if "name" in stream:
                    loc = f"streams[{i}].{stream['name']}"
                else:
                    errors.append(create_error("Missing required field 'name'", loc, "Add 'name' field"))
                
                if "temperature" not in stream:
                    errors.append(create_error("Missing required field 'temperature'", loc, "Add 'temperature' field"))
                if "pressure" not in stream:
                    errors.append(create_error("Missing required field 'pressure'", loc, "Add 'pressure' field"))
                
                if "mass_flow" not in stream and "mole_flow" not in stream:
                     errors.append(create_error("Missing flow specification", loc, "Add either 'mass_flow' or 'mole_flow'"))

    # Blocks
    if "blocks" in spec and isinstance(spec["blocks"], list):
        for i, block in enumerate(spec["blocks"]):
            if isinstance(block, dict):
                loc = f"blocks[{i}]"
                if "name" in block:
                    loc = f"blocks[{i}].{block['name']}"
                else:
                    errors.append(create_error("Missing required field 'name'", loc, "Add 'name' field"))
                
                if "type" not in block:
                    errors.append(create_error("Missing required field 'type'", loc, "Add 'type' field"))

    # Flowsheet
    if "flowsheet" in spec and isinstance(spec["flowsheet"], list):
        for i, entry in enumerate(spec["flowsheet"]):
            if isinstance(entry, dict):
                loc = f"flowsheet[{i}]"
                if "block" not in entry:
                     errors.append(create_error("Missing required field 'block'", loc, "Add 'block' field referencing a block name"))
                if "inputs" not in entry:
                     errors.append(create_error("Missing required field 'inputs'", loc, "Add 'inputs' list"))
                if "outputs" not in entry:
                     errors.append(create_error("Missing required field 'outputs'", loc, "Add 'outputs' list"))

    return errors

def validate_units(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate units against allowed values."""
    errors = []
    if "metadata" in spec and "units" in spec["metadata"]:
        units = spec["metadata"]["units"]
        
        if "pressure" in units and units["pressure"] not in VALID_PRESSURE_UNITS:
            errors.append(create_error(f"Invalid pressure unit '{units['pressure']}'", "metadata.units.pressure", f"Use one of: {', '.join(VALID_PRESSURE_UNITS)}"))
            
        if "temperature" in units and units["temperature"] not in VALID_TEMPERATURE_UNITS:
            errors.append(create_error(f"Invalid temperature unit '{units['temperature']}'", "metadata.units.temperature", f"Use one of: {', '.join(VALID_TEMPERATURE_UNITS)}"))
            
        if "flow" in units and units["flow"] not in VALID_FLOW_UNITS:
            errors.append(create_error(f"Invalid flow unit '{units['flow']}'", "metadata.units.flow", f"Use one of: {', '.join(VALID_FLOW_UNITS)}"))
            
    return errors

def validate_block_references(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate that blocks used in flowsheet are defined in blocks section."""
    errors = []
    defined_blocks = set()
    if "blocks" in spec and isinstance(spec["blocks"], list):
        for block in spec["blocks"]:
            if isinstance(block, dict) and "name" in block:
                defined_blocks.add(block["name"])
    
    if "flowsheet" in spec and isinstance(spec["flowsheet"], list):
        for i, entry in enumerate(spec["flowsheet"]):
            if isinstance(entry, dict) and "block" in entry:
                block_name = entry["block"]
                if block_name not in defined_blocks:
                    errors.append(create_error(f"Undefined block '{block_name}' referenced in flowsheet", f"flowsheet[{i}].block", f"Define block '{block_name}' in the blocks section"))
    
    return errors

def validate_compositions(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate that stream compositions sum to ~1.0."""
    errors = []
    if "streams" in spec and isinstance(spec["streams"], list):
        for i, stream in enumerate(spec["streams"]):
            if isinstance(stream, dict) and "composition" in stream and isinstance(stream["composition"], dict):
                comp_sum = sum(stream["composition"].values())
                if abs(comp_sum - 1.0) > COMPOSITION_TOLERANCE:
                     loc = f"streams[{i}].{stream.get('name', 'unnamed')}.composition"
                     errors.append(create_error(f"Composition sums to {comp_sum}, expected 1.0", loc, "Normalize composition fractions to sum to 1.0"))
    return errors

def validate_stream_connectivity(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate that input streams used in flowsheet are defined feeds or produced internally."""
    errors = []
    defined_streams = set()
    if "streams" in spec and isinstance(spec["streams"], list):
        for stream in spec["streams"]:
             if isinstance(stream, dict) and "name" in stream:
                 defined_streams.add(stream["name"])
    
    produced_streams = set()
    if "flowsheet" in spec and isinstance(spec["flowsheet"], list):
        for entry in spec["flowsheet"]:
            if isinstance(entry, dict) and "outputs" in entry and isinstance(entry["outputs"], list):
                for outstream in entry["outputs"]:
                    produced_streams.add(outstream)

    if "flowsheet" in spec and isinstance(spec["flowsheet"], list):
        for i, entry in enumerate(spec["flowsheet"]):
            if isinstance(entry, dict):
                block_name = entry.get("block", f"block_{i}")
                
                # Check inputs
                if "inputs" in entry and isinstance(entry["inputs"], list):
                    for stream_name in entry["inputs"]:
                        if stream_name not in defined_streams and stream_name not in produced_streams:
                            errors.append(create_error(f"Undefined input stream '{stream_name}' for block '{block_name}'", f"flowsheet[{i}].inputs", f"Define stream '{stream_name}' in the streams section"))

    return errors

def validate_component_references(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate that components referenced in streams/reactions are defined."""
    errors = []
    defined_components = set()
    if "components" in spec and isinstance(spec["components"], list):
        for comp in spec["components"]:
            if isinstance(comp, dict) and "id" in comp:
                defined_components.add(comp["id"])
    
    # Check streams
    if "streams" in spec and isinstance(spec["streams"], list):
        for i, stream in enumerate(spec["streams"]):
             if isinstance(stream, dict) and "composition" in stream and isinstance(stream["composition"], dict):
                 for comp_id in stream["composition"]:
                     if comp_id not in defined_components:
                         loc = f"streams[{i}].{stream.get('name', 'unnamed')}.composition"
                         errors.append(create_error(f"Undefined component '{comp_id}'", loc, f"Define component '{comp_id}' in the components section"))

    # Check chemistry (if exists)
    if "chemistry" in spec and isinstance(spec["chemistry"], list):
         for i, rxn in enumerate(spec["chemistry"]):
             if isinstance(rxn, dict) and "stoichiometry" in rxn and isinstance(rxn["stoichiometry"], dict):
                 for comp_id in rxn["stoichiometry"]:
                     if comp_id not in defined_components:
                          loc = f"chemistry[{i}].stoichiometry"
                          errors.append(create_error(f"Undefined component '{comp_id}' in reaction", loc, f"Define component '{comp_id}' in the components section"))

    return errors

def validate_schema_structure(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate top-level schema structure."""
    errors = []
    required_sections = ["metadata", "components", "properties", "flowsheet", "streams", "blocks"]
    
    if not isinstance(spec, dict):
        return [create_error("Specification must be a dictionary (JSON object/YAML map)", "root", "Check file format integrity", severity="error")]

    for section in required_sections:
        if section not in spec:
            errors.append(create_error(f"Missing required top-level section '{section}'", "root", f"Add '{section}' section to specification"))

    # Check metadata structure specifically
    if "metadata" in spec and isinstance(spec["metadata"], dict):
        if "title" not in spec["metadata"]:
             errors.append(create_error("Missing required field 'title' in metadata", "metadata", "Add 'title' field"))
        if "units" not in spec["metadata"]:
             errors.append(create_error("Missing required field 'units' in metadata", "metadata", "Add 'units' section"))
        elif isinstance(spec["metadata"]["units"], dict):
             for unit_type in ["pressure", "temperature", "flow"]:
                 if unit_type not in spec["metadata"]["units"]:
                     errors.append(create_error(f"Missing required unit definition '{unit_type}'", "metadata.units", f"Define unit for '{unit_type}'"))

    return errors

def validate_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run full validation on the specification.
    
    Returns:
        dict: Validation report with 'valid' boolean and list of 'errors'
    """
    all_errors = []
    
    # Run all validators
    # Order matters slightly: structure -> types -> references -> logic
    
    all_errors.extend(validate_schema_structure(spec))
    if any(e["location"] == "root" for e in all_errors):
         # If root is not a dict, stop immediately
         return {"valid": False, "errors": all_errors}
         
    all_errors.extend(validate_types(spec))
    all_errors.extend(validate_required_fields(spec))
    
    # Only proceed with reference/logic validation if structure/types are mostly sane
    # But for comprehensive reporting, we can try to run them anyway, carefully
    
    all_errors.extend(validate_units(spec))
    all_errors.extend(validate_component_references(spec))
    all_errors.extend(validate_block_references(spec))
    all_errors.extend(validate_stream_connectivity(spec))
    all_errors.extend(validate_compositions(spec))
    
    return {
        "valid": len(all_errors) == 0,
        "errors": all_errors
    }


# --------------------------------------------------------------------------- #
# Schema Definitions (Pydantic Models)
# --------------------------------------------------------------------------- #

class UnitSystem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pressure: str = Field(..., description="Pressure units (e.g., bar, psi, atm, kPa, MPa)")
    temperature: str = Field(..., description="Temperature units (e.g., C, F, K, R)")
    flow: str = Field(..., description="Flow units (e.g., kg/hr, kmol/hr, lb/hr, lbmol/hr)")

class Metadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    description: Optional[str] = None
    units: UnitSystem

class Component(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    formula: Optional[str] = None

class Properties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: str
    databanks: Optional[List[str]] = None

class FlowsheetConnection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    block: str
    inputs: List[str]
    outputs: List[str]

class Stream(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    temperature: float
    pressure: float
    mass_flow: Optional[float] = None
    mole_flow: Optional[float] = None
    composition: Dict[str, float]

    @model_validator(mode='after')
    def check_flow_provided(self) -> 'Stream':
        if self.mass_flow is None and self.mole_flow is None:
            raise ValueError("Either mass_flow or mole_flow must be provided for stream")
        return self

    @field_validator('composition')
    @classmethod
    def validate_composition_sum(cls, v: Dict[str, float]) -> Dict[str, float]:
        total = sum(v.values())
        if not (0.999 <= total <= 1.001):
            raise ValueError(f"Composition sum is {total}, expected 1.0 (±0.001)")
        return v

class Block(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    type: str
    parameters: Optional[Dict[str, Union[float, str]]] = None
    reactions: Optional[str] = None
    split_fractions: Optional[List["SplitFraction"]] = None
    sep_fractions: Optional[List["SepFraction"]] = None

class ChemistryStoichiometry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    component: str
    coefficient: float


class ReactionParameterType(str, enum.Enum):
    EQUIL = "EQUIL"
    KINETIC = "KINETIC"


class ReactionParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reaction_type: ReactionParameterType = ReactionParameterType.EQUIL
    phase: Optional[str] = None

    equilibrium_form: Optional[str] = None
    equilibrium_basis: Optional[str] = None
    equilibrium_constants: Optional[List[float]] = None

    rate_basis: Optional[str] = None
    pre_exponential_factor: Optional[float] = None
    activation_energy: Optional[float] = None
    temperature_exponent: Optional[float] = None

    @field_validator("phase", "equilibrium_form", "equilibrium_basis", "rate_basis")
    @classmethod
    def normalize_string_fields(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty when provided")
        return cleaned.upper()

    @field_validator("equilibrium_constants")
    @classmethod
    def validate_equilibrium_constants(cls, value: Optional[List[float]]) -> Optional[List[float]]:
        if value is None:
            return value
        if len(value) != 4:
            raise ValueError("equilibrium_constants must contain exactly 4 values (A, B, C, D)")
        return value

    @model_validator(mode="after")
    def validate_parameter_consistency(self) -> "ReactionParameters":
        if self.reaction_type == ReactionParameterType.EQUIL:
            if self.pre_exponential_factor is not None or self.activation_energy is not None:
                raise ValueError("pre_exponential_factor and activation_energy are only valid for KINETIC reactions")
            if self.temperature_exponent is not None:
                raise ValueError("temperature_exponent is only valid for KINETIC reactions")
            if self.rate_basis is not None:
                raise ValueError("rate_basis is only valid for KINETIC reactions")

        if self.reaction_type == ReactionParameterType.KINETIC:
            if self.pre_exponential_factor is None or self.activation_energy is None:
                raise ValueError("KINETIC reactions require pre_exponential_factor and activation_energy")
            if self.equilibrium_constants is not None:
                raise ValueError("equilibrium_constants are only valid for EQUIL reactions")
            if self.equilibrium_form is not None or self.equilibrium_basis is not None:
                raise ValueError("equilibrium_form and equilibrium_basis are only valid for EQUIL reactions")

        return self


class Reaction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    stoichiometry: List[ChemistryStoichiometry]
    parameters: Optional[ReactionParameters] = None

class Chemistry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    reactions: List[Reaction]

class ReactionSet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    block_type: str
    reaction_ids: List[int]

class SplitFraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stream: str
    fraction: float

class SepFraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stream: str
    substream: str = "MIXED"
    component: str
    fraction: float

class PurityTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expression: str
    min_value: float

class Targets(BaseModel):
    model_config = ConfigDict(extra="forbid")
    production_rate_tpd: float
    tolerance: float = 0.01
    purity: Optional[PurityTarget] = None

class FlowsheetingOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mass_balance: bool = Field(default=True, description="Enable mass balance calculation")
    energy_balance: bool = Field(default=True, description="Enable energy balance calculation")


class ProcessDefaults(BaseModel):
    """Process-specific defaults stored in the YAML template.

    These values are used as fallbacks when the same information is not
    provided via ``targets`` or inferred from the flowsheet topology.
    All fields are optional so templates can set only what is relevant.
    """
    model_config = ConfigDict(extra="forbid")
    purity_expression: Optional[str] = None
    product_stream: Optional[str] = None
    convergence_block: Optional[str] = None


class PlantSpecification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metadata: Metadata
    components: List[Component]
    properties: Properties

    flowsheeting_options: Optional[FlowsheetingOptions] = None
    process_defaults: Optional[ProcessDefaults] = None
    flowsheet: List[FlowsheetConnection]
    streams: List[Stream]
    blocks: List[Block]
    chemistry: Optional[List[Chemistry]] = None
    reaction_sets: Optional[List[ReactionSet]] = None
    targets: Optional[Targets] = None

Block.model_rebuild()
PlantSpecification.model_rebuild()

