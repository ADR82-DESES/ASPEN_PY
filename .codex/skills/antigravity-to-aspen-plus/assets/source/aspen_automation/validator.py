from typing import Dict, Any, List
from .schema import (
    PlantSpecification,
    VALID_RADFRAC_CONDENSERS,
    VALID_RADFRAC_RATE_BASES,
    VALID_RADFRAC_REBOILERS,
)
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

    # Gather produced streams
    produced_streams = set()
    for conn in spec.flowsheet:
        for outstream in conn.outputs:
            produced_streams.add(outstream)

    # Rule 3: Stream Connectivity
    for i, conn in enumerate(spec.flowsheet):
        for j, instream in enumerate(conn.inputs):
            if instream not in stream_names and instream not in produced_streams:
                add_error("error", f"flowsheet[{i}].inputs[{j}]",
                          f"Undefined input stream '{instream}' for block '{conn.block}'",
                          f"Define stream '{instream}' in the streams section or as an output of another block")

    # Rule 5: Block References
    for i, conn in enumerate(spec.flowsheet):
        if conn.block not in block_names:
            add_error("error", f"flowsheet[{i}].block",
                      f"Block '{conn.block}' referenced but not defined",
                      f"Add block '{conn.block}' to blocks section")

    connections_by_block = {conn.block: conn for conn in spec.flowsheet}

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
    reaction_lookup = {}
    reaction_locations = {}
    if spec.chemistry:
        for i, chem in enumerate(spec.chemistry):
            for j, rxn in enumerate(chem.reactions):
                loc = f"chemistry[{i}].reactions[{j}]"
                if rxn.id in reaction_ids:
                    add_error("error", f"{loc}.id",
                              f"Duplicate reaction ID '{rxn.id}' found",
                              "Ensure each reaction has a unique numeric ID across chemistry sections")
                reaction_ids.add(rxn.id)
                reaction_lookup[rxn.id] = rxn
                reaction_locations[rxn.id] = loc

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
                    continue

                reaction = reaction_lookup.get(rxn_id)
                reaction_loc = reaction_locations.get(rxn_id, f"reaction_id[{rxn_id}]")
                if not reaction:
                    continue

                if rxn_set.block_type.upper() == "REQUIL":
                    if not reaction.parameters:
                        add_error(
                            "error",
                            f"{reaction_loc}.parameters",
                            (
                                f"Reaction ID '{rxn_id}' is used by REQUIL set '{rxn_set.id}' "
                                "but has no equilibrium parameters"
                            ),
                            (
                                "Provide parameters.reaction_type=EQUIL with equilibrium_form, "
                                "equilibrium_basis, and equilibrium_constants"
                            ),
                        )
                        continue

                    if reaction.parameters.reaction_type.value != "EQUIL":
                        add_error(
                            "error",
                            f"{reaction_loc}.parameters.reaction_type",
                            (
                                f"Reaction ID '{rxn_id}' used by REQUIL set '{rxn_set.id}' "
                                "must use EQUIL reaction_type"
                            ),
                            "Set parameters.reaction_type to 'EQUIL' for REQUIL reaction sets",
                        )

                    if not reaction.parameters.equilibrium_form:
                        add_error(
                            "error",
                            f"{reaction_loc}.parameters.equilibrium_form",
                            (
                                f"Reaction ID '{rxn_id}' used by REQUIL set '{rxn_set.id}' "
                                "is missing equilibrium_form"
                            ),
                            "Set parameters.equilibrium_form (for example, 'LNK-1/T')",
                        )

                    if not reaction.parameters.equilibrium_basis:
                        add_error(
                            "error",
                            f"{reaction_loc}.parameters.equilibrium_basis",
                            (
                                f"Reaction ID '{rxn_id}' used by REQUIL set '{rxn_set.id}' "
                                "is missing equilibrium_basis"
                            ),
                            "Set parameters.equilibrium_basis (for example, 'FUGACITY')",
                        )

                    if not reaction.parameters.equilibrium_constants:
                        add_error(
                            "error",
                            f"{reaction_loc}.parameters.equilibrium_constants",
                            (
                                f"Reaction ID '{rxn_id}' used by REQUIL set '{rxn_set.id}' "
                                "is missing equilibrium_constants"
                            ),
                            "Provide four constants in parameters.equilibrium_constants",
                        )

                if reaction.parameters and reaction.parameters.reaction_type.value == "KINETIC":
                    if not reaction.parameters.rate_basis:
                        add_error(
                            "error",
                            f"{reaction_loc}.parameters.rate_basis",
                            f"KINETIC reaction ID '{rxn_id}' is missing rate_basis",
                            "Set parameters.rate_basis (for example, 'MOLARITY')",
                        )

    for i, block in enumerate(spec.blocks):
        if block.reactions and block.reactions not in reaction_set_ids:
            add_error("error", f"blocks[{i}].reactions",
                      f"Reaction set '{block.reactions}' referenced but not defined",
                      "Add the reaction set to reaction_sets or update block.reactions")

        valid_stream_references = stream_names | produced_streams

        if block.split_fractions:
            for j, split in enumerate(block.split_fractions):
                if split.stream not in valid_stream_references:
                    add_error("error", f"blocks[{i}].split_fractions[{j}].stream",
                              f"Stream '{split.stream}' referenced in FSPLIT but not defined",
                              "Add stream to streams section, define it in flowsheet outputs, or update split_fractions")

        if block.sep_fractions:
            for j, sep in enumerate(block.sep_fractions):
                if sep.stream not in valid_stream_references:
                    add_error("error", f"blocks[{i}].sep_fractions[{j}].stream",
                              f"Stream '{sep.stream}' referenced in SEP but not defined",
                              "Add stream to streams section, define it in flowsheet outputs, or update sep_fractions")
                if sep.component not in comp_ids:
                    add_error("error", f"blocks[{i}].sep_fractions[{j}].component",
                              f"Component '{sep.component}' referenced in SEP but not defined",
                              "Add component to components section or update sep_fractions")

        block_type = block.type.upper()
        if block_type == "VALVE":
            parameters = block.parameters or {}
            try:
                p_out = float(parameters.get("P-OUT"))
            except (TypeError, ValueError):
                p_out = None
            if p_out is None or p_out <= 0:
                add_error(
                    "error",
                    f"blocks[{i}].parameters.P-OUT",
                    "VALVE blocks require positive parameters.P-OUT",
                    "Set P-OUT to the target outlet pressure in the spec pressure units",
                )

        if block_type == "RADFRAC":
            radfrac = block.radfrac
            conn = connections_by_block.get(block.name)
            if conn is None:
                add_error(
                    "error",
                    f"blocks[{i}]",
                    f"RADFRAC block '{block.name}' is not referenced in flowsheet",
                    "Add one flowsheet entry with one input and two outputs",
                )
            else:
                if len(conn.inputs) != 1:
                    add_error(
                        "error",
                        f"flowsheet.{block.name}.inputs",
                        "RADFRAC requires exactly one feed stream in this generator",
                        "Use a single material feed to the column",
                    )
                if len(conn.outputs) not in {2, 3}:
                    add_error(
                        "error",
                        f"flowsheet.{block.name}.outputs",
                        "RADFRAC requires two liquid products or a condenser vapor vent plus two liquid products in this generator",
                        "Define distillate/bottoms, or vapor vent/distillate/bottoms products",
                    )

            if radfrac is None:
                add_error(
                    "error",
                    f"blocks[{i}].radfrac",
                    "RADFRAC blocks require complete radfrac settings",
                    "Add n_stages, feed_stage, pressure profile, condenser, reboiler, reflux, and rate spec",
                )
            else:
                if radfrac.n_stages < 3:
                    add_error("error", f"blocks[{i}].radfrac.n_stages", "RADFRAC n_stages must be >= 3", "Use at least 3 stages")
                if not 1 <= radfrac.feed_stage <= radfrac.n_stages:
                    add_error(
                        "error",
                        f"blocks[{i}].radfrac.feed_stage",
                        "RADFRAC feed_stage must be between 1 and n_stages",
                        "Move the feed stage into the column stage range",
                    )
                if radfrac.top_pressure <= 0:
                    add_error("error", f"blocks[{i}].radfrac.top_pressure", "RADFRAC top_pressure must be positive", "Set top pressure in spec pressure units")
                if radfrac.pressure_drop_per_stage < 0:
                    add_error(
                        "error",
                        f"blocks[{i}].radfrac.pressure_drop_per_stage",
                        "RADFRAC pressure_drop_per_stage must be nonnegative",
                        "Use zero or a positive stage pressure drop",
                    )
                if radfrac.condenser not in VALID_RADFRAC_CONDENSERS:
                    add_error("error", f"blocks[{i}].radfrac.condenser", "Unsupported RADFRAC condenser", f"Use one of: {', '.join(VALID_RADFRAC_CONDENSERS)}")
                if radfrac.reboiler not in VALID_RADFRAC_REBOILERS:
                    add_error("error", f"blocks[{i}].radfrac.reboiler", "Unsupported RADFRAC reboiler", f"Use one of: {', '.join(VALID_RADFRAC_REBOILERS)}")
                if radfrac.rate_basis not in VALID_RADFRAC_RATE_BASES:
                    add_error("error", f"blocks[{i}].radfrac.rate_basis", "Unsupported RADFRAC rate_basis", f"Use one of: {', '.join(VALID_RADFRAC_RATE_BASES)}")

    if spec.targets and spec.targets.product_conditions:
        for i, condition in enumerate(spec.targets.product_conditions):
            if condition.stream not in stream_names:
                add_error(
                    "error",
                    f"targets.product_conditions[{i}].stream",
                    f"Product condition references undefined stream '{condition.stream}'",
                    "Reference an existing stream name",
                )

    if spec.targets and spec.targets.component_loss_limits:
        component_names = {component.id for component in spec.components}
        for i, limit in enumerate(spec.targets.component_loss_limits):
            if limit.stream not in stream_names:
                add_error(
                    "error",
                    f"targets.component_loss_limits[{i}].stream",
                    f"Component loss limit references undefined stream '{limit.stream}'",
                    "Reference an existing stream name",
                )
            if limit.component not in component_names:
                add_error(
                    "error",
                    f"targets.component_loss_limits[{i}].component",
                    f"Component loss limit references undefined component '{limit.component}'",
                    "Reference an existing component ID",
                )

    # Rule 4: Composition Validation (Already partially handled by Pydantic validator in schema.py)
    # But we double check here to gather all errors at once if we wanted custom messaging
    # Pydantic's errors were already caught in the try/except block above.

    return report
