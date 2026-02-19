from typing import Dict, Any, List
from .schema import PlantSpecification
from pydantic import ValidationError as PydanticValidationError

def validate_spec(spec_dict: Dict[str, Any]) -> Dict[str, Any]:
    report = {
        "valid": True,
        "errors": []
    }

    def add_error(severity, location, message, suggestion):
        report["errors"].append({
            "severity": severity,
            "location": location,
            "message": message,
            "suggestion": suggestion
        })
        if severity == "error":
            report["valid"] = False

    # Rule 1 & 7 & 8: Schema Structure, Required Fields, and Type Validation (via Pydantic)
    try:
        spec = PlantSpecification(**spec_dict)
    except PydanticValidationError as e:
        for error in e.errors():
            loc = ".".join(str(x) for x in error["loc"])
            msg = error["msg"]
            add_error("error", loc, msg, f"Check the field '{loc}' for correct type or presence")
        # If schema is basically broken, we can't run other rules
        return report

    # If Pydantic passed, we can do deeper cross-reference validation
    
    # Rule 9: Duplicate Detection
    seen_comp_ids = set()
    for i, comp in enumerate(spec.components):
        if comp.id in seen_comp_ids:
            add_error("error", f"components[{i}]", 
                      f"Duplicate component ID '{comp.id}' found", 
                      "Ensure each component has a unique ID")
        seen_comp_ids.add(comp.id)

    seen_stream_names = set()
    for i, stream in enumerate(spec.streams):
        if stream.name in seen_stream_names:
            add_error("error", f"streams[{i}]", 
                      f"Duplicate stream name '{stream.name}' found", 
                      "Ensure each stream name is unique")
        seen_stream_names.add(stream.name)

    seen_block_names = set()
    for i, block in enumerate(spec.blocks):
        if block.name in seen_block_names:
            add_error("error", f"blocks[{i}]", 
                      f"Duplicate block name '{block.name}' found", 
                      "Ensure each block name is unique")
        seen_block_names.add(block.name)

    # Pre-build sets for fast lookup (Rule 2-5)
    comp_ids = seen_comp_ids
    stream_names = seen_stream_names
    block_names = seen_block_names

    # Rule 2: Component References
    for i, stream in enumerate(spec.streams):
        for comp_id in stream.composition.keys():
            if comp_id not in comp_ids:
                add_error("error", f"streams[{i}].composition.{comp_id}", 
                          f"Component '{comp_id}' used but not defined",
                          f"Add component '{comp_id}' to components section")

    if spec.chemistry:
        for i, chem in enumerate(spec.chemistry):
            for j, rxn in enumerate(chem.reactions):
                for k, stoic in enumerate(rxn.stoichiometry):
                    if stoic.component not in comp_ids:
                        add_error("error", f"chemistry[{i}].reactions[{j}].stoichiometry[{k}]",
                                  f"Component '{stoic.component}' used in reaction but not defined",
                                  f"Add component '{stoic.component}' to components section")

    # Rule 3: Stream Connectivity
    for i, conn in enumerate(spec.flowsheet):
        for j, instream in enumerate(conn.inputs):
            if instream not in stream_names:
                add_error("error", f"flowsheet[{i}].inputs[{j}]",
                          f"Stream '{instream}' referenced but not defined",
                          f"Add stream '{instream}' to streams section")
        for j, outstream in enumerate(conn.outputs):
            if outstream not in stream_names:
                add_error("error", f"flowsheet[{i}].outputs[{j}]",
                          f"Stream '{outstream}' referenced but not defined",
                          f"Add stream '{outstream}' to streams section")

    # Rule 5: Block References
    for i, conn in enumerate(spec.flowsheet):
        if conn.block not in block_names:
            add_error("error", f"flowsheet[{i}].block",
                      f"Block '{conn.block}' referenced but not defined",
                      f"Add block '{conn.block}' to blocks section")

    # Rule 6: Unit Validation (case-insensitive)
    allowed_pressure = {"bar", "psi", "atm", "kpa", "mpa"}
    allowed_temperature = {"c", "f", "k", "r"}
    allowed_flow = {"kg/hr", "kmol/hr", "lb/hr", "lbmol/hr"}

    units = spec.metadata.units
    pressure_norm = units.pressure.lower()
    temperature_norm = units.temperature.lower()
    flow_norm = units.flow.lower()

    if pressure_norm not in allowed_pressure:
        add_error("error", "metadata.units.pressure",
                  f"Invalid unit '{units.pressure}' for pressure",
                  f"Use one of: {', '.join(sorted(allowed_pressure))}")
    
    if temperature_norm not in allowed_temperature:
        add_error("error", "metadata.units.temperature",
                  f"Invalid unit '{units.temperature}' for temperature",
                  f"Use one of: {', '.join(sorted(allowed_temperature))}")
                  
    if flow_norm not in allowed_flow:
        add_error("error", "metadata.units.flow",
                  f"Invalid unit '{units.flow}' for flow",
                  f"Use one of: {', '.join(sorted(allowed_flow))}")

    # Reaction set validation (optional)
    reaction_ids = set()
    if spec.chemistry:
        for chem in spec.chemistry:
            for rxn in chem.reactions:
                reaction_ids.add(rxn.id)

    reaction_set_ids = set()
    if spec.reaction_sets:
        for i, rxn_set in enumerate(spec.reaction_sets):
            if rxn_set.id in reaction_set_ids:
                add_error("error", f"reaction_sets[{i}].id",
                          f"Duplicate reaction set ID '{rxn_set.id}' found",
                          "Ensure each reaction set has a unique ID")
            reaction_set_ids.add(rxn_set.id)
            for j, rxn_id in enumerate(rxn_set.reaction_ids):
                if rxn_id not in reaction_ids:
                    add_error("error", f"reaction_sets[{i}].reaction_ids[{j}]",
                              f"Reaction ID '{rxn_id}' referenced but not defined in chemistry",
                              "Add the reaction ID to a chemistry section or update reaction_ids")

    for i, block in enumerate(spec.blocks):
        if block.reactions and block.reactions not in reaction_set_ids:
            add_error("error", f"blocks[{i}].reactions",
                      f"Reaction set '{block.reactions}' referenced but not defined",
                      "Add the reaction set to reaction_sets or update block.reactions")

        if block.split_fractions:
            for j, split in enumerate(block.split_fractions):
                if split.stream not in stream_names:
                    add_error("error", f"blocks[{i}].split_fractions[{j}].stream",
                              f"Stream '{split.stream}' referenced in FSPLIT but not defined",
                              "Add stream to streams section or update split_fractions")

        if block.sep_fractions:
            for j, sep in enumerate(block.sep_fractions):
                if sep.stream not in stream_names:
                    add_error("error", f"blocks[{i}].sep_fractions[{j}].stream",
                              f"Stream '{sep.stream}' referenced in SEP but not defined",
                              "Add stream to streams section or update sep_fractions")
                if sep.component not in comp_ids:
                    add_error("error", f"blocks[{i}].sep_fractions[{j}].component",
                              f"Component '{sep.component}' referenced in SEP but not defined",
                              "Add component to components section or update sep_fractions")

    # Rule 4: Composition Validation (Already partially handled by Pydantic validator in schema.py)
    # But we double check here to gather all errors at once if we wanted custom messaging
    # Pydantic's errors were already caught in the try/except block above.

    return report
