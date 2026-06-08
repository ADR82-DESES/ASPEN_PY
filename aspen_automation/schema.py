from typing import Any, Dict, List, Optional, Union
import math
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
import enum

# Constants
VALID_PRESSURE_UNITS = ["bar", "psi", "atm", "kPa", "MPa"]
VALID_TEMPERATURE_UNITS = ["C", "F", "K", "R"]
VALID_FLOW_UNITS = ["kg/hr", "kmol/hr", "lb/hr", "lbmol/hr"]
VALID_PROPERTY_METHODS = ["RK-SOAVE", "IDEAL", "NRTL", "UNIQUAC", "PENG-ROB", "SRK"]
VALID_BLOCK_TYPES = [
    "MIXER",
    "RGIBBS",
    "HEATER",
    "FLASH2",
    "COMPR",
    "REQUIL",
    "RPLUG",
    "FSPLIT",
    "SEP",
    "RADFRAC",
    "VALVE",
]
VALID_RATE_BASES = ["MOLEFRAC", "MASSFRAC", "MOLARITY", "MOLALITY", "MASSCONC", "PARTIALPRES"]
VALID_BINARY_PARAMETER_SOURCE_TYPES = ["aspen_databank", "explicit"]
VALID_RADFRAC_CONDENSERS = ["TOTAL", "PARTIAL-V"]
VALID_RADFRAC_REBOILERS = ["KETTLE"]
VALID_RADFRAC_RATE_BASES = ["MASS", "MOLE"]
VALID_NRTL_BINARY_PARAMETER_FIELDS = [
    "aij", "aji", "bij", "bji", "cij", "dij",
    "eij", "eji", "fij", "fji", "t_lower", "t_upper",
]
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
                if field in stream and stream[field] is not None and not isinstance(stream[field], (int, float)):
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

def validate_binary_parameters(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate source-tagged binary property parameter declarations."""
    errors = []
    properties = spec.get("properties")
    if not isinstance(properties, dict):
        return errors

    binary_parameters = properties.get("binary_parameters")
    if binary_parameters is None:
        return errors

    if not isinstance(binary_parameters, list):
        return [
            create_error(
                "Field 'binary_parameters' must be a list",
                "properties.binary_parameters",
                "Define binary parameters as a list of component-pair records",
            )
        ]

    allowed_fields = set(VALID_NRTL_BINARY_PARAMETER_FIELDS)
    allowed_source_types = set(VALID_BINARY_PARAMETER_SOURCE_TYPES)
    defined_components = {
        comp.get("id")
        for comp in spec.get("components", [])
        if isinstance(comp, dict) and isinstance(comp.get("id"), str)
    }
    defined_components_upper = {comp.upper() for comp in defined_components}

    for index, entry in enumerate(binary_parameters):
        loc = f"properties.binary_parameters[{index}]"
        if not isinstance(entry, dict):
            errors.append(create_error("Binary parameter entry must be a dictionary", loc))
            continue

        components = entry.get("components")
        if not isinstance(components, list) or len(components) != 2:
            errors.append(
                create_error(
                    "Binary parameter entry must define exactly two components",
                    f"{loc}.components",
                    "Use components: [COMP1, COMP2]",
                )
            )
        else:
            cleaned = []
            for component in components:
                if not isinstance(component, str) or not component.strip():
                    errors.append(
                        create_error(
                            "Binary parameter component identifiers must be non-empty strings",
                            f"{loc}.components",
                        )
                    )
                    continue
                cleaned.append(component.strip().upper())
            if len(cleaned) == 2 and cleaned[0] == cleaned[1]:
                errors.append(create_error("Binary parameter pair must contain two distinct components", f"{loc}.components"))
            for component in cleaned:
                if defined_components_upper and component not in defined_components_upper:
                    errors.append(
                        create_error(
                            f"Undefined component '{component}' in binary parameter pair",
                            f"{loc}.components",
                            f"Define component '{component}' in components or correct the pair",
                        )
                    )

        provenance = entry.get("provenance")
        if not isinstance(provenance, dict) or not str(provenance.get("source", "")).strip():
            errors.append(
                create_error(
                    "Binary parameter entries require provenance.source",
                    f"{loc}.provenance",
                    "Add a source citation, databank reference, or local verification note",
                )
            )

        source_type = str(entry.get("source_type", "aspen_databank")).strip()
        if source_type not in allowed_source_types:
            errors.append(
                create_error(
                    f"Unsupported binary parameter source_type '{source_type}'",
                    f"{loc}.source_type",
                    f"Use one of: {', '.join(VALID_BINARY_PARAMETER_SOURCE_TYPES)}",
                )
            )

        if source_type == "aspen_databank":
            databanks = entry.get("databanks")
            if not isinstance(databanks, list) or not any(str(db).strip() for db in databanks):
                errors.append(
                    create_error(
                        "Databank-backed binary parameters require at least one databank",
                        f"{loc}.databanks",
                        "List the Aspen databank(s) that provide the interaction parameters",
                    )
                )

        values = entry.get("values")
        if values is not None:
            if not isinstance(values, dict):
                errors.append(create_error("Binary parameter values must be a dictionary", f"{loc}.values"))
            else:
                unsupported = sorted(set(values) - allowed_fields)
                if unsupported:
                    errors.append(
                        create_error(
                            f"Unsupported NRTL binary parameter field(s): {', '.join(unsupported)}",
                            f"{loc}.values",
                            f"Use only: {', '.join(VALID_NRTL_BINARY_PARAMETER_FIELDS)}",
                        )
                    )
                for field, value in values.items():
                    if field in allowed_fields and not isinstance(value, (int, float)):
                        errors.append(
                            create_error(
                                f"Binary parameter value '{field}' must be numeric",
                                f"{loc}.values.{field}",
                            )
                        )
        elif source_type == "explicit":
            errors.append(
                create_error(
                    "Explicit binary parameters require numeric values",
                    f"{loc}.values",
                    "Provide verified NRTL parameter values or use source_type: aspen_databank",
                )
            )

    return errors

def _normalized_block_type(block: Dict[str, Any]) -> str:
    return str(block.get("type", "")).strip().upper()

def _numeric_value(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        converted = float(value)
        if math.isfinite(converted):
            return converted
    return None

def validate_distillation_blocks(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate supported RADFRAC and pressure-letdown block declarations."""
    errors: List[Dict[str, Any]] = []
    blocks = spec.get("blocks")
    flowsheet = spec.get("flowsheet")
    if not isinstance(blocks, list):
        return errors

    connections_by_block: Dict[str, Dict[str, Any]] = {}
    if isinstance(flowsheet, list):
        for connection in flowsheet:
            if isinstance(connection, dict) and isinstance(connection.get("block"), str):
                connections_by_block[connection["block"].upper()] = connection

    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        block_type = _normalized_block_type(block)
        loc = f"blocks[{index}].{block.get('name', 'unnamed')}"

        if block_type == "VALVE":
            parameters = block.get("parameters")
            if not isinstance(parameters, dict):
                errors.append(create_error("VALVE blocks require parameters", f"{loc}.parameters", "Add parameters: {'P-OUT': <bar>}"))
                continue
            outlet_pressure = _numeric_value(parameters.get("P-OUT"))
            if outlet_pressure is None or outlet_pressure <= 0:
                errors.append(create_error("VALVE blocks require positive parameters.P-OUT", f"{loc}.parameters.P-OUT", "Set P-OUT to the target outlet pressure in the spec pressure units"))

        if block_type != "RADFRAC":
            if "radfrac" in block and block.get("radfrac") is not None:
                errors.append(create_error("Only RADFRAC blocks may define radfrac settings", f"{loc}.radfrac"))
            continue

        radfrac = block.get("radfrac")
        if not isinstance(radfrac, dict):
            errors.append(create_error("RADFRAC blocks require a radfrac settings section", f"{loc}.radfrac", "Add column stages, pressure profile, condenser, reboiler, and rate specs"))
            continue

        connection = connections_by_block.get(str(block.get("name", "")).upper())
        if not isinstance(connection, dict):
            errors.append(create_error("RADFRAC block is not referenced in the flowsheet", loc, "Add a flowsheet entry for this block"))
        else:
            inputs = connection.get("inputs")
            outputs = connection.get("outputs")
            if not isinstance(inputs, list) or len(inputs) != 1:
                errors.append(create_error("RADFRAC requires exactly one feed stream in this generator", f"flowsheet[{block.get('name')}].inputs"))
            if not isinstance(outputs, list) or len(outputs) not in {2, 3}:
                errors.append(create_error("RADFRAC requires two liquid products or vapor vent plus two liquid products in this generator", f"flowsheet[{block.get('name')}].outputs"))

        n_stages = _numeric_value(radfrac.get("n_stages"))
        feed_stage = _numeric_value(radfrac.get("feed_stage"))
        top_pressure = _numeric_value(radfrac.get("top_pressure"))
        pressure_drop = _numeric_value(radfrac.get("pressure_drop_per_stage"))
        reflux_ratio = _numeric_value(radfrac.get("reflux_ratio"))
        max_outer = _numeric_value(radfrac.get("max_outer_iterations"))
        bottoms_rate = _numeric_value(radfrac.get("bottoms_rate"))
        distillate_rate = _numeric_value(radfrac.get("distillate_rate"))

        if n_stages is None or n_stages < 3 or not n_stages.is_integer():
            errors.append(create_error("RADFRAC n_stages must be an integer >= 3", f"{loc}.radfrac.n_stages"))
        if feed_stage is None or not feed_stage.is_integer() or (n_stages is not None and not (1 <= feed_stage <= n_stages)):
            errors.append(create_error("RADFRAC feed_stage must be an integer between 1 and n_stages", f"{loc}.radfrac.feed_stage"))
        if top_pressure is None or top_pressure <= 0:
            errors.append(create_error("RADFRAC top_pressure must be positive", f"{loc}.radfrac.top_pressure"))
        if pressure_drop is None or pressure_drop < 0:
            errors.append(create_error("RADFRAC pressure_drop_per_stage must be nonnegative", f"{loc}.radfrac.pressure_drop_per_stage"))
        if reflux_ratio is None or reflux_ratio <= 0:
            errors.append(create_error("RADFRAC reflux_ratio must be positive", f"{loc}.radfrac.reflux_ratio"))
        if max_outer is None or max_outer < 1 or not max_outer.is_integer():
            errors.append(create_error("RADFRAC max_outer_iterations must be a positive integer", f"{loc}.radfrac.max_outer_iterations"))
        if (bottoms_rate is None) == (distillate_rate is None):
            errors.append(create_error("RADFRAC requires exactly one of bottoms_rate or distillate_rate", f"{loc}.radfrac"))
        if bottoms_rate is not None and bottoms_rate <= 0:
            errors.append(create_error("RADFRAC bottoms_rate must be positive", f"{loc}.radfrac.bottoms_rate"))
        if distillate_rate is not None and distillate_rate <= 0:
            errors.append(create_error("RADFRAC distillate_rate must be positive", f"{loc}.radfrac.distillate_rate"))

        condenser = str(radfrac.get("condenser", "")).strip().upper()
        reboiler = str(radfrac.get("reboiler", "")).strip().upper()
        rate_basis = str(radfrac.get("rate_basis", "")).strip().upper()
        if condenser not in VALID_RADFRAC_CONDENSERS:
            errors.append(create_error(f"Unsupported RADFRAC condenser '{radfrac.get('condenser')}'", f"{loc}.radfrac.condenser", f"Use one of: {', '.join(VALID_RADFRAC_CONDENSERS)}"))
        if reboiler not in VALID_RADFRAC_REBOILERS:
            errors.append(create_error(f"Unsupported RADFRAC reboiler '{radfrac.get('reboiler')}'", f"{loc}.radfrac.reboiler", f"Use one of: {', '.join(VALID_RADFRAC_REBOILERS)}"))
        if rate_basis not in VALID_RADFRAC_RATE_BASES:
            errors.append(create_error(f"Unsupported RADFRAC rate_basis '{radfrac.get('rate_basis')}'", f"{loc}.radfrac.rate_basis", f"Use one of: {', '.join(VALID_RADFRAC_RATE_BASES)}"))

        if n_stages is not None and top_pressure is not None and pressure_drop is not None:
            bottom_pressure = top_pressure + pressure_drop * (n_stages - 1)
            if bottom_pressure + 1e-12 < top_pressure:
                errors.append(create_error("RADFRAC bottom pressure must be greater than or equal to top pressure", f"{loc}.radfrac.pressure_drop_per_stage"))

    return errors

def validate_product_conditions(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    errors: List[Dict[str, Any]] = []
    targets = spec.get("targets")
    if not isinstance(targets, dict):
        return errors
    product_conditions = targets.get("product_conditions")
    if product_conditions is None:
        return errors
    if not isinstance(product_conditions, list):
        return [create_error("targets.product_conditions must be a list", "targets.product_conditions")]
    defined_streams = {
        stream.get("name")
        for stream in spec.get("streams", [])
        if isinstance(stream, dict) and isinstance(stream.get("name"), str)
    }
    defined_streams_upper = {stream.upper() for stream in defined_streams}
    for index, condition in enumerate(product_conditions):
        loc = f"targets.product_conditions[{index}]"
        if not isinstance(condition, dict):
            errors.append(create_error("Product condition entry must be a dictionary", loc))
            continue
        stream = str(condition.get("stream", "")).strip()
        if not stream:
            errors.append(create_error("Product condition requires stream", f"{loc}.stream"))
        elif defined_streams_upper and stream.upper() not in defined_streams_upper:
            errors.append(create_error(f"Product condition references undefined stream '{stream}'", f"{loc}.stream"))
        pressure = condition.get("pressure")
        if pressure is not None:
            pressure_value = _numeric_value(pressure)
            tolerance_value = _numeric_value(condition.get("pressure_tolerance", 0.05))
            if pressure_value is None or pressure_value <= 0:
                errors.append(create_error("Product condition pressure must be positive", f"{loc}.pressure"))
            if tolerance_value is None or tolerance_value < 0:
                errors.append(create_error("Product condition pressure_tolerance must be nonnegative", f"{loc}.pressure_tolerance"))
        temperature = condition.get("temperature")
        if temperature is not None:
            if _numeric_value(temperature) is None:
                errors.append(create_error("Product condition temperature must be numeric", f"{loc}.temperature"))
            tolerance_value = _numeric_value(condition.get("temperature_tolerance", 1.0))
            if tolerance_value is None or tolerance_value < 0:
                errors.append(create_error("Product condition temperature_tolerance must be nonnegative", f"{loc}.temperature_tolerance"))
    return errors

def validate_component_loss_limits(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    errors: List[Dict[str, Any]] = []
    targets = spec.get("targets")
    if not isinstance(targets, dict):
        return errors
    limits = targets.get("component_loss_limits")
    if limits is None:
        return errors
    if not isinstance(limits, list):
        return [create_error("targets.component_loss_limits must be a list", "targets.component_loss_limits")]

    defined_streams = {
        stream.get("name")
        for stream in spec.get("streams", [])
        if isinstance(stream, dict) and isinstance(stream.get("name"), str)
    }
    defined_streams_upper = {stream.upper() for stream in defined_streams}
    defined_components = {
        component.get("id")
        for component in spec.get("components", [])
        if isinstance(component, dict) and isinstance(component.get("id"), str)
    }
    defined_components_upper = {component.upper() for component in defined_components}

    for index, limit in enumerate(limits):
        loc = f"targets.component_loss_limits[{index}]"
        if not isinstance(limit, dict):
            errors.append(create_error("Component loss limit entry must be a dictionary", loc))
            continue

        stream = str(limit.get("stream", "")).strip()
        component = str(limit.get("component", "")).strip()
        if not stream:
            errors.append(create_error("Component loss limit requires stream", f"{loc}.stream"))
        elif defined_streams_upper and stream.upper() not in defined_streams_upper:
            errors.append(create_error(f"Component loss limit references undefined stream '{stream}'", f"{loc}.stream"))

        if not component:
            errors.append(create_error("Component loss limit requires component", f"{loc}.component"))
        elif defined_components_upper and component.upper() not in defined_components_upper:
            errors.append(create_error(f"Component loss limit references undefined component '{component}'", f"{loc}.component"))

        max_kg_hr = _numeric_value(limit.get("max_kg_hr"))
        max_tpd = _numeric_value(limit.get("max_tpd"))
        if (max_kg_hr is None) == (max_tpd is None):
            errors.append(create_error("Component loss limit requires exactly one of max_kg_hr or max_tpd", loc))
        if max_kg_hr is not None and max_kg_hr < 0:
            errors.append(create_error("Component loss max_kg_hr must be nonnegative", f"{loc}.max_kg_hr"))
        if max_tpd is not None and max_tpd < 0:
            errors.append(create_error("Component loss max_tpd must be nonnegative", f"{loc}.max_tpd"))

        baseline_kg_hr = _numeric_value(limit.get("baseline_kg_hr"))
        baseline_tpd = _numeric_value(limit.get("baseline_tpd"))
        if baseline_kg_hr is not None and baseline_kg_hr <= 0:
            errors.append(create_error("Component loss baseline_kg_hr must be positive", f"{loc}.baseline_kg_hr"))
        if baseline_tpd is not None and baseline_tpd <= 0:
            errors.append(create_error("Component loss baseline_tpd must be positive", f"{loc}.baseline_tpd"))
        if baseline_kg_hr is not None and baseline_tpd is not None:
            errors.append(create_error("Component loss limit accepts only one baseline field", loc))

        basis = str(limit.get("basis", "mass")).strip().lower()
        if basis != "mass":
            errors.append(create_error("Component loss limit currently supports only basis: mass", f"{loc}.basis"))

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
    """Compatibility wrapper for the canonical validator implementation.

    Keep this import path working for older callers, but route all full-spec
    validation through ``aspen_automation.validator.validate_spec`` so schema
    and validator reports cannot diverge.
    """
    from .validator import validate_spec as _canonical_validate_spec

    return _canonical_validate_spec(spec)


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

class BinaryParameterProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    reference: Optional[str] = None
    locator: Optional[str] = None
    notes: Optional[str] = None
    verified_by: Optional[str] = None
    verified_on: Optional[str] = None

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("provenance.source cannot be empty")
        return cleaned

class BinaryParameter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    components: List[str]
    model: str = "NRTL"
    source_type: str = "aspen_databank"
    parameter_set: Optional[str] = None
    databanks: Optional[List[str]] = None
    values: Optional[Dict[str, float]] = None
    units: Optional[Dict[str, str]] = None
    basis: Optional[str] = None
    provenance: BinaryParameterProvenance

    @field_validator("components")
    @classmethod
    def validate_components(cls, value: List[str]) -> List[str]:
        if len(value) != 2:
            raise ValueError("binary parameter components must contain exactly two entries")
        cleaned = [component.strip().upper() for component in value]
        if any(not component for component in cleaned):
            raise ValueError("binary parameter components cannot be empty")
        if cleaned[0] == cleaned[1]:
            raise ValueError("binary parameter components must be distinct")
        return cleaned

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if cleaned != "NRTL":
            raise ValueError("only NRTL binary parameters are currently supported")
        return cleaned

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, value: str) -> str:
        cleaned = value.strip()
        if cleaned not in VALID_BINARY_PARAMETER_SOURCE_TYPES:
            allowed = ", ".join(VALID_BINARY_PARAMETER_SOURCE_TYPES)
            raise ValueError(f"source_type must be one of: {allowed}")
        return cleaned

    @field_validator("values")
    @classmethod
    def validate_values(cls, value: Optional[Dict[str, float]]) -> Optional[Dict[str, float]]:
        if value is None:
            return value
        unsupported = sorted(set(value) - set(VALID_NRTL_BINARY_PARAMETER_FIELDS))
        if unsupported:
            raise ValueError(f"unsupported NRTL binary parameter field(s): {', '.join(unsupported)}")
        return value

    @model_validator(mode="after")
    def validate_source_payload(self) -> "BinaryParameter":
        if self.source_type == "aspen_databank" and not self.databanks:
            raise ValueError("databank-backed binary parameters require databanks")
        if self.source_type == "explicit" and not self.values:
            raise ValueError("explicit binary parameters require values")
        return self

class Properties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: str
    databanks: Optional[List[str]] = None
    binary_parameters: Optional[List[BinaryParameter]] = None

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
    radfrac: Optional["RadFracSpec"] = None

    @field_validator("type")
    @classmethod
    def validate_block_type(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if cleaned not in VALID_BLOCK_TYPES:
            allowed = ", ".join(VALID_BLOCK_TYPES)
            raise ValueError(f"block type must be one of: {allowed}")
        return cleaned

    @model_validator(mode="after")
    def validate_model_specific_payload(self) -> "Block":
        block_type = self.type.upper()
        if block_type == "RADFRAC":
            if self.radfrac is None:
                raise ValueError("RADFRAC blocks require radfrac settings")
            if self.split_fractions or self.sep_fractions:
                raise ValueError("RADFRAC blocks cannot define split_fractions or sep_fractions")
        elif self.radfrac is not None:
            raise ValueError("radfrac settings are only valid for RADFRAC blocks")

        if block_type == "VALVE":
            parameters = self.parameters or {}
            outlet_pressure = parameters.get("P-OUT")
            if outlet_pressure is None:
                raise ValueError("VALVE blocks require parameters.P-OUT")
            try:
                pressure = float(outlet_pressure)
            except (TypeError, ValueError) as exc:
                raise ValueError("VALVE parameters.P-OUT must be numeric") from exc
            if pressure <= 0:
                raise ValueError("VALVE parameters.P-OUT must be positive")
        return self

class ChemistryStoichiometry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    component: str
    coefficient: float


class ReactionParameterType(str, enum.Enum):
    EQUIL = "EQUIL"
    KINETIC = "KINETIC"
    LHHW = "LHHW"


class LhhwKineticFactor(BaseModel):
    """Kinetic factor k = k0·exp[-(E/R)(1/T - 1/T_ref)] (reference-T Arrhenius)."""
    model_config = ConfigDict(extra="forbid")
    pre_exp: float
    act_energy: float
    act_energy_unit: str = "kcal/mol"
    t_ref: Optional[float] = None


def _validate_coeff_length(value: List[float]) -> List[float]:
    if len(value) > 4:
        raise ValueError("coeff accepts at most 4 values (A, B, C, D)")
    return value


class LhhwDrivingForceTerm(BaseModel):
    """One driving-force term: Π p_j^exponent times K = exp(A + B/T + C·lnT + D·T)."""
    model_config = ConfigDict(extra="forbid")
    exponents: Dict[str, float] = Field(default_factory=dict)
    coeff: List[float] = Field(default_factory=list)  # [A, B, C, D]; trailing entries omittable

    @field_validator("coeff")
    @classmethod
    def _check_coeff(cls, value: List[float]) -> List[float]:
        return _validate_coeff_length(value)


class LhhwDrivingForce(BaseModel):
    model_config = ConfigDict(extra="forbid")
    term1: LhhwDrivingForceTerm
    term2: LhhwDrivingForceTerm


class LhhwAdsorptionTerm(BaseModel):
    """One adsorption-denominator term coefficient K = exp(A + B/T + C·lnT + D·T)."""
    model_config = ConfigDict(extra="forbid")
    coeff: List[float] = Field(default_factory=list)  # [A, B, C, D]

    @field_validator("coeff")
    @classmethod
    def _check_coeff(cls, value: List[float]) -> List[float]:
        return _validate_coeff_length(value)


class LhhwAdsorption(BaseModel):
    """Adsorption denominator: (Σ_t K_t · Π p_j^exp_{t,j})^power."""
    model_config = ConfigDict(extra="forbid")
    power: float = 1.0
    terms: List[LhhwAdsorptionTerm]
    exponents: Dict[str, List[float]] = Field(default_factory=dict)  # component -> per-term vector
    conc_basis: str = "PARTIALPRES"

    @model_validator(mode="after")
    def _check_vectors(self) -> "LhhwAdsorption":
        n = len(self.terms)
        if n == 0:
            raise ValueError("adsorption.terms must contain at least one term")
        if self.power <= 0:
            raise ValueError("adsorption.power must be positive")
        for component, vector in self.exponents.items():
            if len(vector) != n:
                raise ValueError(
                    f"adsorption.exponents['{component}'] must have {n} values "
                    "(one per adsorption term)"
                )
        return self


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

    # LHHW rate-law blocks
    kinetic_factor: Optional[LhhwKineticFactor] = None
    driving_force: Optional[LhhwDrivingForce] = None
    adsorption: Optional[LhhwAdsorption] = None
    # LHHW REAC-DATA attributes (defaults applied at emit time)
    name: Optional[str] = None
    conc_basis: Optional[str] = None
    cat_basis: Optional[str] = None
    reversible: Optional[bool] = None
    rev_method: Optional[str] = None
    pres_unit: Optional[str] = None

    @field_validator("phase", "equilibrium_form", "equilibrium_basis", "rate_basis",
                     "conc_basis", "cat_basis", "rev_method", "pres_unit")
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
            if self.rate_basis is not None and self.rate_basis not in VALID_RATE_BASES:
                allowed = ", ".join(VALID_RATE_BASES)
                raise ValueError(f"rate_basis must be one of: {allowed}")

        if self.reaction_type == ReactionParameterType.LHHW:
            missing = [
                field
                for field, value in (
                    ("kinetic_factor", self.kinetic_factor),
                    ("driving_force", self.driving_force),
                    ("adsorption", self.adsorption),
                )
                if value is None
            ]
            if missing:
                raise ValueError(f"LHHW reactions require: {', '.join(missing)}")
            forbidden = [
                field
                for field, value in (
                    ("pre_exponential_factor", self.pre_exponential_factor),
                    ("activation_energy", self.activation_energy),
                    ("temperature_exponent", self.temperature_exponent),
                    ("rate_basis", self.rate_basis),
                    ("equilibrium_constants", self.equilibrium_constants),
                    ("equilibrium_form", self.equilibrium_form),
                    ("equilibrium_basis", self.equilibrium_basis),
                )
                if value is not None
            ]
            if forbidden:
                raise ValueError(
                    f"These fields are not valid for LHHW reactions: {', '.join(forbidden)}"
                )
        else:
            lhhw_blocks = [
                field
                for field, value in (
                    ("kinetic_factor", self.kinetic_factor),
                    ("driving_force", self.driving_force),
                    ("adsorption", self.adsorption),
                )
                if value is not None
            ]
            if lhhw_blocks:
                raise ValueError(
                    f"{', '.join(lhhw_blocks)} are only valid for LHHW reactions"
                )

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

class RadFracSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n_stages: int
    feed_stage: int
    condenser: str
    reboiler: str
    top_pressure: float
    pressure_drop_per_stage: float
    reflux_ratio: float
    bottoms_rate: Optional[float] = None
    distillate_rate: Optional[float] = None
    rate_basis: str
    max_outer_iterations: int

    @field_validator("condenser")
    @classmethod
    def validate_condenser(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if cleaned not in VALID_RADFRAC_CONDENSERS:
            allowed = ", ".join(VALID_RADFRAC_CONDENSERS)
            raise ValueError(f"condenser must be one of: {allowed}")
        return cleaned

    @field_validator("reboiler")
    @classmethod
    def validate_reboiler(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if cleaned not in VALID_RADFRAC_REBOILERS:
            allowed = ", ".join(VALID_RADFRAC_REBOILERS)
            raise ValueError(f"reboiler must be one of: {allowed}")
        return cleaned

    @field_validator("rate_basis")
    @classmethod
    def validate_rate_basis(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if cleaned not in VALID_RADFRAC_RATE_BASES:
            allowed = ", ".join(VALID_RADFRAC_RATE_BASES)
            raise ValueError(f"rate_basis must be one of: {allowed}")
        return cleaned

    @model_validator(mode="after")
    def validate_column_specs(self) -> "RadFracSpec":
        if self.n_stages < 3:
            raise ValueError("n_stages must be >= 3")
        if not 1 <= self.feed_stage <= self.n_stages:
            raise ValueError("feed_stage must be between 1 and n_stages")
        if self.top_pressure <= 0:
            raise ValueError("top_pressure must be positive")
        if self.pressure_drop_per_stage < 0:
            raise ValueError("pressure_drop_per_stage must be nonnegative")
        if self.reflux_ratio <= 0:
            raise ValueError("reflux_ratio must be positive")
        if self.max_outer_iterations < 1:
            raise ValueError("max_outer_iterations must be positive")
        has_bottoms = self.bottoms_rate is not None
        has_distillate = self.distillate_rate is not None
        if has_bottoms == has_distillate:
            raise ValueError("exactly one of bottoms_rate or distillate_rate must be provided")
        if self.bottoms_rate is not None and self.bottoms_rate <= 0:
            raise ValueError("bottoms_rate must be positive")
        if self.distillate_rate is not None and self.distillate_rate <= 0:
            raise ValueError("distillate_rate must be positive")
        return self

class PurityTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expression: str
    min_value: float

class ProductConditionTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stream: str
    pressure: Optional[float] = None
    pressure_tolerance: float = 0.05
    temperature: Optional[float] = None
    temperature_tolerance: float = 1.0

    @field_validator("stream")
    @classmethod
    def validate_stream(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("stream cannot be empty")
        return cleaned

    @model_validator(mode="after")
    def validate_conditions(self) -> "ProductConditionTarget":
        if self.pressure is None and self.temperature is None:
            raise ValueError("at least one of pressure or temperature must be provided")
        if self.pressure is not None and self.pressure <= 0:
            raise ValueError("pressure must be positive")
        if self.pressure_tolerance < 0:
            raise ValueError("pressure_tolerance must be nonnegative")
        if self.temperature_tolerance < 0:
            raise ValueError("temperature_tolerance must be nonnegative")
        return self

class ComponentLossLimitTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stream: str
    component: str
    max_kg_hr: Optional[float] = None
    max_tpd: Optional[float] = None
    basis: str = "mass"
    description: Optional[str] = None
    baseline_kg_hr: Optional[float] = None
    baseline_tpd: Optional[float] = None

    @field_validator("stream", "component")
    @classmethod
    def validate_nonempty_identifier(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value cannot be empty")
        return cleaned

    @field_validator("basis")
    @classmethod
    def validate_basis(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned != "mass":
            raise ValueError("only basis: mass is currently supported")
        return cleaned

    @model_validator(mode="after")
    def validate_limit(self) -> "ComponentLossLimitTarget":
        has_kg_hr = self.max_kg_hr is not None
        has_tpd = self.max_tpd is not None
        if has_kg_hr == has_tpd:
            raise ValueError("exactly one of max_kg_hr or max_tpd must be provided")
        if self.max_kg_hr is not None and self.max_kg_hr < 0:
            raise ValueError("max_kg_hr must be nonnegative")
        if self.max_tpd is not None and self.max_tpd < 0:
            raise ValueError("max_tpd must be nonnegative")
        has_baseline_kg_hr = self.baseline_kg_hr is not None
        has_baseline_tpd = self.baseline_tpd is not None
        if has_baseline_kg_hr and has_baseline_tpd:
            raise ValueError("only one baseline field may be provided")
        if self.baseline_kg_hr is not None and self.baseline_kg_hr <= 0:
            raise ValueError("baseline_kg_hr must be positive")
        if self.baseline_tpd is not None and self.baseline_tpd <= 0:
            raise ValueError("baseline_tpd must be positive")
        return self

class Targets(BaseModel):
    model_config = ConfigDict(extra="forbid")
    production_rate_tpd: float
    tolerance: float = 0.01
    purity: Optional[PurityTarget] = None
    product_conditions: Optional[List[ProductConditionTarget]] = None
    component_loss_limits: Optional[List[ComponentLossLimitTarget]] = None

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
    kinetic_models: Optional[List[Dict[str, Any]]] = None
    flowsheet: List[FlowsheetConnection]
    streams: List[Stream]
    blocks: List[Block]
    chemistry: Optional[List[Chemistry]] = None
    reaction_sets: Optional[List[ReactionSet]] = None
    targets: Optional[Targets] = None

Block.model_rebuild()
PlantSpecification.model_rebuild()
