from typing import List, Optional, Dict, Any, Tuple, Union
import time
import warnings

from .exceptions import ValidationError
from .schema import (
    PlantSpecification,
    Stream,
    Block,
    Component,
    Chemistry,
    FlowsheetConnection,
    Properties,
    Reaction,
    ReactionParameterType,
    ReactionParameters,
    ReactionSet,
)
from .validator import validate_spec

DEFAULT_DATABANKS = [
    "PURE32",
    "AQUEOUS",
    "SOLIDS",
    "INORGANIC",
    "NOASPENPCD",
]

# Aspen's NRTL BPVAL is DIRECTIONAL: "BPVAL c1 c2 ..." fills only the forward (i->j)
# elements in this positional order, and the reverse (j->i) params are set by a second
# "BPVAL c2 c1 ..." line. Verified live against the VLE-IG databank gamma.
NRTL_BPVAL_FORWARD_ORDER = ["aij", "bij", "cij", "dij", "eij", "fij"]
NRTL_BPVAL_REVERSE_ORDER = ["aji", "bji", "cij", "dij", "eji", "fji"]
NRTL_UNSUPPORTED_EXPLICIT_FIELDS = ("t_lower", "t_upper")

PRESSURE_UNITS = {
    "bar": "BAR",
    "psi": "PSI",
    "atm": "ATM",
    "kpa": "KPA",
    "mpa": "MPA",
}

TEMPERATURE_UNITS = {
    "c": "C",
    "f": "F",
    "k": "K",
    "r": "R",
}

FLOW_UNITS = {
    "kg/hr": "KG/HR",
    "kmol/hr": "KMOL/HR",
    "lb/hr": "LB/HR",
    "lbmol/hr": "LBMOL/HR",
}

TOP_LEVEL_KEYWORDS = (
    "TITLE",
    "IN-UNITS",
    "DEF-STREAMS",
    "DATABANKS",
    "PROP-SOURCES",
    "COMPONENTS",
    "PROPERTIES",
    "FLOWSHEET",
    "STREAM",
    "BLOCK",
    "CHEMISTRY",
    "REACTIONS",
)

REQUIRED_SECTION_ORDER = [
    "TITLE",
    "IN-UNITS",
    "DEF-STREAMS",
    "DATABANKS",
    "PROP-SOURCES",
    "COMPONENTS",
    "PROPERTIES",
    "FLOWSHEET",
    "STREAM",
    "BLOCK",
]

OPTIONAL_SECTION_ORDER = [
    "CHEMISTRY",
    "REACTIONS",
]

ALL_SECTION_ORDER = [
    "TITLE",
    "IN-UNITS",
    "DEF-STREAMS",
    "DATABANKS",
    "PROP-SOURCES",
    "COMPONENTS",
    "PROPERTIES",
    "FLOWSHEET",
    "STREAM",
    "BLOCK",
    "CHEMISTRY",
    "REACTIONS",
]

UNSUPPORTED_BLOCK_TYPE_ERRORS: Dict[str, Tuple[str, str]] = {}


def generate_inp(spec: Union[PlantSpecification, Dict[str, Any]], output_path: Optional[str] = None) -> str:
    """
    Generates an Aspen Plus .inp file based on the PlantSpecification.
    """
    spec_obj = _ensure_spec(spec)

    if not spec_obj.streams:
        raise ValidationError("Spec must contain at least one stream", {"valid": False, "errors": [{"severity": "error", "message": "Spec must contain at least one stream"}]})
    if not spec_obj.blocks:
        raise ValidationError("Spec must contain at least one block", {"valid": False, "errors": [{"severity": "error", "message": "Spec must contain at least one block"}]})
    _validate_generator_compatibility(spec_obj)

    profile_generation = len(spec_obj.blocks) >= 100 or len(spec_obj.flowsheet) >= 100
    start_time = time.perf_counter() if profile_generation else None

    sections: List[str] = []

    # 1. Title
    sections.append(_generate_title(spec_obj.metadata.title))

    # Optional description comments (Move after Title)
    if spec_obj.metadata.description:
        sections.append(_generate_comments(spec_obj.metadata.description))

    # 2. IN-UNITS
    sections.append(_generate_in_units(spec_obj.metadata.units))

    # 3. DEF-STREAMS
    sections.append("DEF-STREAMS CONVEN ALL")

    # 4. DATABANKS & PROP-SOURCES
    db_sections = _generate_databanks(spec_obj.properties)
    if db_sections:
        sections.extend(db_sections)

    # 5. COMPONENTS
    sections.append(_generate_components(spec_obj.components))

    # 6. PROPERTIES
    sections.append(f"PROPERTIES {spec_obj.properties.method}")

    # 6b. Explicit binary-parameter PROP-DATA blocks (baked-in NRTL values)
    sections.extend(_generate_binary_parameters(spec_obj.properties))


    # 7. FLOWSHEET
    sections.append(_generate_flowsheet(spec_obj.flowsheet))

    # 8. STREAM
    for stream in spec_obj.streams:
        sections.append(_generate_stream(stream))

    # 9. BLOCK
    reaction_lookup = _build_reaction_lookup(spec_obj.chemistry)
    reaction_set_lookup = {
        reaction_set.id: reaction_set
        for reaction_set in (spec_obj.reaction_sets or [])
    }
    flowsheet_by_block = {conn.block.upper(): conn for conn in spec_obj.flowsheet}
    for block in spec_obj.blocks:
        sections.append(
            _generate_block(
                block,
                reaction_set_lookup,
                reaction_lookup,
                flowsheet_by_block.get(block.name.upper()),
            )
        )

    # 10. CHEMISTRY (Optional)
    #
    # POWERLAW/LHHW/USER reaction paragraphs carry their own STOIC data. Emitting
    # those same kinetic reactions in a standalone CHEMISTRY paragraph makes
    # Aspen's batch translator treat them like global chemistry and can raise
    # equilibrium-style dependency warnings. Keep CHEMISTRY for standalone/REQUIL
    # chemistry, but let rate-controlled reaction sets own their stoichiometry.
    kinetic_reaction_ids = _reaction_ids_for_non_requil_sets(spec_obj.reaction_sets)
    if spec_obj.chemistry:
        for chemistry in spec_obj.chemistry:
            section = _generate_chemistry(chemistry, exclude_reaction_ids=kinetic_reaction_ids)
            if section:
                sections.append(section)

    # 11. REACTIONS (Optional)
    if spec_obj.reaction_sets:
        for reaction_set in spec_obj.reaction_sets:
            reaction_section = _generate_reactions(reaction_set, reaction_lookup)
            if reaction_section:
                sections.append(reaction_section)

    inp_content = "\n\n".join(sections) + "\n"
    validation_report = validate_inp(inp_content)
    if not validation_report["valid"]:
        raise ValidationError("Generated INP failed validation", validation_report)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(inp_content)

    if profile_generation and start_time is not None:
        elapsed = time.perf_counter() - start_time
        warnings.warn(
            f"INP generation time: {elapsed:.3f}s for {len(spec_obj.blocks)} blocks and {len(spec_obj.flowsheet)} flowsheet connections",
            RuntimeWarning,
        )

    return inp_content


def _validate_generator_compatibility(spec_obj: PlantSpecification) -> None:
    errors: List[Dict[str, Any]] = []

    for index, block in enumerate(spec_obj.blocks):
        block_type = block.type.upper()
        unsupported = UNSUPPORTED_BLOCK_TYPE_ERRORS.get(block_type)
        if unsupported is None:
            continue

        message, suggestion = unsupported
        errors.append(
            {
                "severity": "error",
                "location": f"blocks[{index}].type",
                "message": message,
                "suggestion": suggestion,
            }
        )

    for index, entry in enumerate(spec_obj.properties.binary_parameters or []):
        if entry.source_type != "explicit":
            continue
        # The directional two-line BPVAL emitter handles aij..fji. Temperature limits
        # use a separate Aspen syntax that is not emitted, so reject them explicitly.
        unsupported_fields = sorted(set(entry.values or {}) & set(NRTL_UNSUPPORTED_EXPLICIT_FIELDS))
        if unsupported_fields:
            errors.append(
                {
                    "severity": "error",
                    "location": f"properties.binary_parameters[{index}].values",
                    "message": (
                        f"Explicit NRTL emission does not yet support temperature-limit field(s) "
                        f"{', '.join(unsupported_fields)}; only the coefficients aij..fji are written."
                    ),
                    "suggestion": (
                        "Omit t_lower/t_upper, or extend _generate_binary_parameters with a verified "
                        "Aspen syntax before specifying them."
                    ),
                }
            )

    if errors:
        raise ValidationError("Generator compatibility validation failed.", {"valid": False, "errors": errors})


def _ensure_spec(spec: Union[PlantSpecification, Dict[str, Any]]) -> PlantSpecification:
    if isinstance(spec, PlantSpecification):
        report = validate_spec(spec.model_dump())
        if not report["valid"]:
            raise ValidationError("Validation failed", report)
        _warn_optional_fields(spec)
        return spec

    if isinstance(spec, dict):
        report = validate_spec(spec)
        if not report["valid"]:
            raise ValidationError("Validation failed", report)
        spec_obj = PlantSpecification(**spec)
        _warn_optional_fields(spec_obj)
        return spec_obj

    raise TypeError("spec must be a PlantSpecification or a dict")


def _warn_optional_fields(spec: PlantSpecification) -> None:
    if not spec.properties.databanks:
        warnings.warn("No databanks specified; using default databanks.", UserWarning)
    if not spec.chemistry and spec.reaction_sets:
        warnings.warn("Reaction sets provided without chemistry definitions.", UserWarning)
    if spec.chemistry and not spec.reaction_sets:
        warnings.warn("Chemistry provided without reaction sets; REACTIONS section will be omitted.", UserWarning)


def _build_reaction_lookup(chemistry_sections: Optional[List[Chemistry]]) -> Dict[int, Reaction]:
    lookup: Dict[int, Reaction] = {}
    if not chemistry_sections:
        return lookup
    for chemistry in chemistry_sections:
        for reaction in chemistry.reactions:
            lookup[reaction.id] = reaction
    return lookup


def _generate_title(title: str) -> str:
    safe_title = title.replace("'", "''")
    return f"TITLE '{safe_title}'"


def _normalize_unit(value: str, mapping: Dict[str, str], field_name: str) -> str:
    key = value.strip().lower()
    if key not in mapping:
        allowed = ", ".join(sorted(mapping.keys()))
        raise ValueError(f"Invalid unit '{value}' for {field_name}. Allowed: {allowed}")
    return mapping[key]


def _generate_in_units(units) -> str:
    u_press = _normalize_unit(units.pressure, PRESSURE_UNITS, "pressure")
    u_temp = _normalize_unit(units.temperature, TEMPERATURE_UNITS, "temperature")
    u_flow = _normalize_unit(units.flow, FLOW_UNITS, "flow")

    # Determine base Aspen unit system.
    # ENG for PSI/F combinations OR English flow units.
    # SI for K (unless overridden by English units? - logic says SI if flow not English and temp K)
    # Actually, if flow is English, we probably want ENG system to allow those units naturally without warnings?
    # The requirement is: "Treat any flow unit in {'LB/HR','LBMOL/HR'} as English and set system='ENG'"

    is_english_flow = u_flow in ("LB/HR", "LBMOL/HR")

    if u_press == "PSI" or u_temp == "F" or u_temp == "R" or is_english_flow:
        system = "ENG"
    elif u_temp == "K":
        system = "SI"
    else:
        system = "MET"

    return (
        f"IN-UNITS {system} "
        f"PRESSURE={u_press} "
        f"TEMPERATURE={u_temp} "
        f"FLOW='{u_flow}'"
    )


def _quote_databank(name: str) -> str:
    cleaned = name.strip().strip("'")
    return f"'{cleaned}'"


def _format_continuation_section(header: str, items: List[str], items_per_line: int = 3) -> List[str]:
    if not items:
        return [header]

    groups = [items[i:i + items_per_line] for i in range(0, len(items), items_per_line)]
    lines: List[str] = []
    indent = " " * 8

    for idx, group in enumerate(groups):
        segment = " / ".join(group)
        is_last = idx == len(groups) - 1
        if idx == 0:
            line = f"{header} {segment}"
        else:
            line = f"{indent}{segment}"

        if not is_last:
            line += " / &"
        lines.append(line)

    return lines


def _generate_databanks(props: Properties) -> List[str]:
    # Default databanks for Aspen V14 if not specified
    db_list = list(props.databanks or [
        'APV140 PURE32', 'APV140 AQUEOUS', 'APV140 SOLIDS',
        'APV140 INORGANIC'
    ])

    for db in _binary_parameter_databanks(props):
        if not any(existing.strip().upper() == db.strip().upper() for existing in db_list):
            db_list.append(db)

    # Ensure NOASPENPCD is at the end if not present
    if not any("NOASPENPCD" in db.upper() for db in db_list):
        db_list.append("NOASPENPCD")

    quoted = [_quote_databank(db) for db in db_list]

    # Filter out NOASPENPCD and other non-sources from PROP-SOURCES
    prop_sources = [db for db in quoted if "NOASPENPCD" not in db.upper()]

    databank_lines = _format_continuation_section("DATABANKS", quoted)
    prop_lines = _format_continuation_section("PROP-SOURCES", prop_sources)

    return ["\n".join(databank_lines), "\n".join(prop_lines)]


def _binary_parameter_databanks(props: Properties) -> List[str]:
    databanks: List[str] = []
    for entry in props.binary_parameters or []:
        if entry.source_type != "aspen_databank":
            continue
        for databank in entry.databanks or []:
            cleaned = databank.strip()
            if cleaned and not any(existing.upper() == cleaned.upper() for existing in databanks):
                databanks.append(cleaned)
    return databanks


def _format_param_value(value: float) -> str:
    """Render a numeric parameter for an Aspen BPVAL line (always a real, never sci)."""
    text = f"{float(value):.10g}"
    if "." not in text and "e" not in text and "E" not in text:
        text += ".0"
    return text


def _trim_trailing_zeros(values: List[float]) -> List[float]:
    out = list(values)
    while out and out[-1] == 0.0:
        out.pop()
    return out


def _generate_binary_parameters(props: Properties) -> List[str]:
    """Emit PROP-DATA blocks for explicit NRTL binary parameters.

    Aspen's NRTL ``BPVAL`` is directional: ``BPVAL c1 c2 ...`` fills the forward
    (i->j) elements positionally as [aij, bij, cij, dij, eij, fij], so the reverse
    (j->i) parameters must be written on a second ``BPVAL c2 c1 ...`` line. Writing
    all five [aij, aji, bij, bji, cij] on one line mis-maps them (aji->bij,
    bij->alpha). Verified live: this two-line form reproduces the databank gamma.

    Explicit values are baked into the deck so they survive into the COM run, whose
    engine cannot retrieve VLE-databank parameters under the virtualized environment.
    """
    sections: List[str] = []
    explicit_index = 0
    for entry in props.binary_parameters or []:
        if entry.source_type != "explicit":
            continue
        explicit_index += 1
        values = entry.values or {}
        comp_i, comp_j = entry.components

        forward = _trim_trailing_zeros(
            [float(values.get(field, 0.0)) for field in NRTL_BPVAL_FORWARD_ORDER]
        )
        # The reverse line only needs aji/bji unless the rarer eji/fji terms are set;
        # those sit at reverse slots 5-6 and require the symmetric cij/dij as padding.
        if values.get("eji", 0.0) or values.get("fji", 0.0):
            reverse = _trim_trailing_zeros(
                [float(values.get(field, 0.0)) for field in NRTL_BPVAL_REVERSE_ORDER]
            )
        else:
            reverse = _trim_trailing_zeros(
                [float(values.get("aji", 0.0)), float(values.get("bji", 0.0))]
            )

        lines = [f"PROP-DATA NRTL-{explicit_index}", "    PROP-LIST NRTL"]
        if forward:
            lines.append(f"    BPVAL {comp_i} {comp_j} " + " ".join(_format_param_value(v) for v in forward))
        if reverse:
            lines.append(f"    BPVAL {comp_j} {comp_i} " + " ".join(_format_param_value(v) for v in reverse))
        sections.append("\n".join(lines))
    return sections


def _generate_flowsheeting_options(options: Optional[Any]) -> str:
    # Default behavior if options is None
    mass_bal = "YES"
    energy_bal = "YES"

    if options:
        mass_bal = "YES" if options.mass_balance else "NO"
        energy_bal = "YES" if options.energy_balance else "NO"

    return "\n".join(
        [
            "FLOWSHEETING-OPTIONS",
            f"    MASS-BAL={mass_bal} ENERGY-BAL={energy_bal}",
        ]
    )



def _generate_components(components: List[Component]) -> str:
    lines = ["COMPONENTS"]
    for comp in components:
        line = f"    {comp.id} {comp.name}"
        if comp.formula:
            line += f" {comp.formula}"
        lines.append(line + " /")
    return "\n".join(lines)


def _format_stream_list(label: str, names: List[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return f"{label}={names[0]}"
    return f"{label}={names[0]} " + " ".join(names[1:])


def _generate_flowsheet(flowsheet) -> str:
    lines = ["FLOWSHEET"]
    for conn in flowsheet:
        in_part = _format_stream_list("IN", conn.inputs)
        out_part = _format_stream_list("OUT", conn.outputs)
        parts = [p for p in (in_part, out_part) if p]
        suffix = " ".join(parts)
        lines.append(f"    BLOCK {conn.block} {suffix}".rstrip())
    return "\n".join(lines)


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "YES" if value else "NO"
    if isinstance(value, (int, float)):
        if isinstance(value, int):
            value = float(value)
        return str(value)
    return str(value)


def _wrap_slash_items(prefix: str, items: List[str], *, indent: str = "    ", width: int = 100) -> List[str]:
    if not items:
        return [indent + prefix.rstrip()]

    lines: List[str] = []
    current = indent + prefix
    continuation_indent = indent + "    "

    for index, item in enumerate(items):
        separator = "" if current.endswith(" ") else " / "
        candidate = f"{current}{separator}{item}"
        if len(candidate) > width and current.strip() != prefix.strip():
            lines.append(current + " / &")
            current = continuation_indent + item
        else:
            current = candidate

    lines.append(current)
    return lines


def _format_stoichiometry_items(reaction: Reaction) -> List[str]:
    return [
        f"{item.component} {_format_value(item.coefficient)}"
        for item in reaction.stoichiometry
    ]


def _format_requil_stoichiometry_items(reaction: Reaction) -> List[str]:
    return [
        f"CID={item.component} COEF={_format_value(item.coefficient)}"
        for item in reaction.stoichiometry
    ]


def _generate_stream(stream: Stream) -> str:
    if stream.mass_flow is None and stream.mole_flow is None:
        raise ValueError(f"Stream '{stream.name}' must have mass_flow or mole_flow")

    lines = [f"STREAM {stream.name}"]

    flow_type = "MASS-FLOW" if stream.mass_flow is not None else "MOLE-FLOW"
    flow_val = stream.mass_flow if stream.mass_flow is not None else stream.mole_flow

    lines.append(
        f"    SUBSTREAM MIXED TEMP={_format_value(stream.temperature)} "
        f"PRES={_format_value(stream.pressure)} "
        f"{flow_type}={_format_value(flow_val)}"
    )

    comp_items = list(stream.composition.items())
    if comp_items:
        composition_items = [f"{comp_id} {_format_value(val)}" for comp_id, val in comp_items]
        lines.extend(_wrap_slash_items("MOLE-FRAC ", composition_items))

    return "\n".join(lines)


def _generate_block(
    block: Block,
    reaction_sets: Optional[Dict[str, ReactionSet]] = None,
    reaction_lookup: Optional[Dict[int, Reaction]] = None,
    flowsheet_connection: Optional[FlowsheetConnection] = None,
) -> str:
    block_type = block.type.upper()

    lines = [f"BLOCK {block.name} {block_type}"]

    if block_type == "VALVE":
        lines.extend(_generate_valve_block(block))
        return "\n".join(lines)

    if block_type == "FSPLIT":
        lines.extend(_generate_fsplit_block(block))
        return "\n".join(lines)

    if block_type == "SEP":
        lines.extend(_generate_sep_block(block))
        return "\n".join(lines)

    if block_type == "RPLUG":
        lines.extend(_generate_rplug_block(block))
        return "\n".join(lines)

    if block_type == "RADFRAC":
        lines.extend(_generate_radfrac_block(block, flowsheet_connection))
        return "\n".join(lines)

    if block.parameters:
        _BLOCK_PARAM_REMAPS = {
            "COMPR": {"EFF": "SEFF"},
        }
        remap = _BLOCK_PARAM_REMAPS.get(block_type, {})
        mapped_params = {}
        for k, v in block.parameters.items():
            key = k.upper()
            mapped_params[remap.get(key, key)] = v
        lines.extend(_generate_param_lines(mapped_params))

    if block.reactions and block_type == "REQUIL":
        reaction_set = (reaction_sets or {}).get(block.reactions)
        lookup = reaction_lookup or {}
        reactions = [
            lookup[rxn_id]
            for rxn_id in (reaction_set.reaction_ids if reaction_set else [])
            if rxn_id in lookup
        ]
        if reactions:
            if not block.parameters:
                lines.extend(_generate_param_lines({"NREAC": 1}))
            elif not any("NREAC" in line.upper() for line in lines):
                lines[-1] = f"{lines[-1]} NREAC={_format_value(1)}"
            if len(reactions) > 1:
                warnings.warn(
                    "Aspen batch INP emission currently supports one REQUIL "
                    f"stoichiometric reaction per block; block '{block.name}' "
                    "will emit the first reaction only.",
                    UserWarning,
                )
            lines.extend(_wrap_slash_items("STOIC ", _format_requil_stoichiometry_items(reactions[0])))
        return "\n".join(lines)

    if block.reactions:
        lines.append(f"    REACTIONS {block.reactions}")

    return "\n".join(lines)


def _generate_valve_block(block: Block) -> List[str]:
    parameters = {str(k).upper(): v for k, v in (block.parameters or {}).items()}
    return _generate_param_lines({"P-OUT": parameters["P-OUT"]})


def _generate_radfrac_block(
    block: Block,
    flowsheet_connection: Optional[FlowsheetConnection],
) -> List[str]:
    if block.radfrac is None:
        raise ValueError(f"RADFRAC block '{block.name}' requires radfrac settings")
    if flowsheet_connection is None:
        raise ValueError(f"RADFRAC block '{block.name}' requires a flowsheet connection")
    if len(flowsheet_connection.inputs) != 1 or len(flowsheet_connection.outputs) not in {2, 3}:
        raise ValueError(
            f"RADFRAC block '{block.name}' requires one feed and two or three product streams"
        )

    radfrac = block.radfrac
    feed_stream = flowsheet_connection.inputs[0]
    if len(flowsheet_connection.outputs) == 3:
        vapor_vent_stream, distillate_stream, bottoms_stream = flowsheet_connection.outputs
        product_line = (
            f"    PRODUCTS {vapor_vent_stream} 1 V / "
            f"{distillate_stream} 1 L / {bottoms_stream} {radfrac.n_stages} L"
        )
    else:
        distillate_stream, bottoms_stream = flowsheet_connection.outputs
        product_line = f"    PRODUCTS {distillate_stream} 1 L / {bottoms_stream} {radfrac.n_stages} L"
    total_pressure_drop = radfrac.pressure_drop_per_stage * (radfrac.n_stages - 1)

    lines = [
        "    PARAM "
        f"NSTAGE={radfrac.n_stages} "
        "ALGORITHM=STANDARD "
        f"MAXOL={radfrac.max_outer_iterations} "
        "DAMPING=NONE",
        f"    COL-CONFIG CONDENSER={radfrac.condenser}",
        f"    FEEDS {feed_stream} {radfrac.feed_stage}",
        product_line,
        f"    P-SPEC 1 {_format_value(radfrac.top_pressure)}",
    ]

    col_specs: Dict[str, Any] = {"DP-COL": total_pressure_drop}
    basis_prefix = "MASS" if radfrac.rate_basis == "MASS" else "MOLE"
    if radfrac.bottoms_rate is not None:
        col_specs[f"{basis_prefix}-B"] = radfrac.bottoms_rate
    elif radfrac.distillate_rate is not None:
        col_specs[f"{basis_prefix}-D"] = radfrac.distillate_rate
    col_specs[f"{basis_prefix}-RR"] = radfrac.reflux_ratio

    lines.append(
        "    COL-SPECS "
        + " ".join(f"{key}={_format_value(value)}" for key, value in col_specs.items())
    )
    lines.append("    TRAY-REPORT TRAY-OPTION=ALL-TRAYS")

    if block.reactions:
        lines.append(f"    REACTIONS {block.reactions}")

    return lines


def _generate_rplug_block(block: Block) -> List[str]:
    parameters = {str(k).upper(): v for k, v in (block.parameters or {}).items()}
    param_line: Dict[str, Any] = {}

    rplug_type = parameters.get("TYPE")
    if rplug_type is None and parameters.get("TEMP") is not None:
        rplug_type = "T-SPEC"
    if rplug_type is None:
        rplug_type = "ADIABATIC"
    param_line["TYPE"] = rplug_type

    for source, target in (
        ("LENGTH", "LENGTH"),
        ("DIAM", "DIAM"),
        ("NTUBE", "NTUBE"),
        ("PRES", "PRES"),
        ("NPOINT", "NPOINT"),
        ("NSEG", "NPOINT"),
        ("NPHASE", "NPHASE"),
        ("MAX-NSTEP", "MAX-NSTEP"),
        ("INT-TOL", "INT-TOL"),
    ):
        if source in parameters and target not in param_line:
            param_line[target] = parameters[source]

    # Catalyst loading. Aspen requires at least TWO of {catalyst loading, bed voidage,
    # catalyst density} when a catalyst is present (ZURE04.29), so emit every one supplied.
    catalyst_params = (("CAT-WT", "CATWT"), ("BED-VOIDAGE", "BED-VOIDAGE"), ("CAT-DENSITY", "CAT-DENSITY"))
    present_catalyst = [(src, tgt) for src, tgt in catalyst_params if src in parameters]
    if present_catalyst:
        param_line["CAT-PRESENT"] = "YES"
        for src, tgt in present_catalyst:
            param_line[tgt] = parameters[src]

    lines = [_generate_rplug_param_line(param_line)]

    if str(rplug_type).upper() == "T-SPEC" and parameters.get("TEMP") is not None:
        temp = _format_value(parameters["TEMP"])
        lines.append(f"    T-SPEC 0.0 {temp} / 1.0 {temp}")

    if block.reactions:
        lines.append(f"    REACTIONS {block.reactions}")

    return lines


def _generate_rplug_param_line(parameters: Dict[str, Any]) -> str:
    integer_keys = {"NPOINT", "NTUBE", "NPHASE", "MAX-NSTEP"}
    assignments = []
    for key, value in parameters.items():
        if key in integer_keys:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                assignments.append(f"{key}={_format_value(value)}")
                continue
            if numeric.is_integer():
                assignments.append(f"{key}={int(numeric)}")
                continue
        assignments.append(f"{key}={_format_value(value)}")
    return "    PARAM " + " ".join(assignments)


def _generate_fsplit_block(block: Block) -> List[str]:
    lines: List[str] = []
    fractions: List[Tuple[str, Any]] = []

    if block.split_fractions:
        fractions = [(f.stream, f.fraction) for f in block.split_fractions]
    elif block.parameters:
        fractions = [(k, v) for k, v in block.parameters.items()]

    for stream_name, fraction in fractions:
        lines.append(f"    FRAC {stream_name} {_format_value(fraction)}")

    return lines


def _generate_sep_block(block: Block) -> List[str]:
    lines: List[str] = []

    if block.parameters:
        lines.extend(_generate_param_lines({k.upper(): v for k, v in block.parameters.items()}))

    if block.sep_fractions:
        grouped_fractions: Dict[str, List[Tuple[str, Any]]] = {}
        for frac in block.sep_fractions:
            grouped_fractions.setdefault(frac.stream, []).append((frac.component, frac.fraction))

        for stream_name, values in grouped_fractions.items():
            comps = " ".join(component for component, _ in values)
            fracs = " ".join(_format_value(fraction) for _, fraction in values)
            lines.append(
                "    FRAC "
                f"STRM={stream_name} "
                f"COMPS={comps} "
                f"FRACS={fracs}"
            )

    if block.reactions:
        lines.append(f"    REACTIONS {block.reactions}")

    return lines


def _generate_param_lines(parameters: Dict[str, Any]) -> List[str]:
    assignments = [f"{key}={_format_value(value)}" for key, value in parameters.items()]
    return ["    PARAM " + " ".join(assignments)]


def _reaction_ids_for_non_requil_sets(reaction_sets: Optional[List[ReactionSet]]) -> set[int]:
    ids: set[int] = set()
    for reaction_set in reaction_sets or []:
        if reaction_set.block_type.upper() == "REQUIL":
            continue
        ids.update(reaction_set.reaction_ids)
    return ids


def _generate_chemistry(chem: Chemistry, exclude_reaction_ids: Optional[set[int]] = None) -> str:
    excluded = exclude_reaction_ids or set()
    reactions = [reaction for reaction in chem.reactions if reaction.id not in excluded]
    if not reactions:
        return ""

    lines = [f"CHEMISTRY {chem.id}"]
    for reaction in reactions:
        lines.extend(_wrap_slash_items(f"STOIC {reaction.id} ", _format_stoichiometry_items(reaction)))
    return "\n".join(lines)


def _generate_reac_data_line(rxn_id: int, params: Optional[ReactionParameters]) -> str:
    parts = [f"    REAC-DATA {rxn_id}"]
    if not params:
        return parts[0]

    parts.append(params.reaction_type.value)
    if params.phase:
        parts.append(f"PHASE={params.phase}")
    if params.equilibrium_basis:
        parts.append(f"KBASIS={params.equilibrium_basis}")
    if params.equilibrium_form:
        parts.append(f"KFORM={params.equilibrium_form}")
    if params.rate_basis:
        parts.append(f"CBASIS={params.rate_basis}")
    return " ".join(parts)

def _set_is_lhhw(reaction_set: ReactionSet, reaction_lookup: Dict[int, Reaction]) -> bool:
    for rid in reaction_set.reaction_ids:
        reaction = reaction_lookup.get(rid)
        params = reaction.parameters if reaction else None
        if params and params.reaction_type == ReactionParameterType.LHHW:
            return True
    return False


def _generate_reactions(reaction_set: ReactionSet, reaction_lookup: Dict[int, Reaction]) -> str:
    block_type = reaction_set.block_type.upper()
    if block_type == "REQUIL":
        return ""

    if _set_is_lhhw(reaction_set, reaction_lookup):
        return _generate_lhhw_reactions(reaction_set, reaction_lookup)

    lines = [f"REACTIONS {reaction_set.id} {block_type}"]
    for rxn_id in reaction_set.reaction_ids:
        reaction = reaction_lookup.get(rxn_id)
        params = reaction.parameters if reaction else None
        lines.append(_generate_reac_data_line(rxn_id, params))
        if reaction is not None:
            lines.extend(_wrap_slash_items(f"STOIC {rxn_id} MIXED ", _format_stoichiometry_items(reaction)))
        lines.extend(_generate_reaction_parameter_lines(rxn_id, params))
    return "\n".join(lines)


def _generate_reaction_parameter_lines(rxn_id: int, params: Optional[ReactionParameters]) -> List[str]:
    if not params:
        return []

    lines: List[str] = []
    if params.equilibrium_constants:
        constants = " ".join(_format_value(val) for val in params.equilibrium_constants)
        lines.append(f"    K-STOIC {rxn_id} {constants}")

    if params.pre_exponential_factor is not None and params.activation_energy is not None:
        rate_values = [
            _format_value(params.pre_exponential_factor),
            _format_value(params.activation_energy),
        ]
        if params.temperature_exponent is not None:
            rate_values.append(_format_value(params.temperature_exponent))
        lines.append(f"    RATE-CON {rxn_id} {' '.join(rate_values)}")

    return lines


def _format_coeff(coeff: List[float]) -> str:
    """Render an LHHW coefficient list as 'A=.. B=.. C=.. D=..' for the values provided."""
    labels = ["A", "B", "C", "D"]
    return " ".join(f"{labels[i]}={_format_value(value)}" for i, value in enumerate(coeff))


def _generate_lhhw_reactions(reaction_set: ReactionSet, reaction_lookup: Dict[int, Reaction]) -> str:
    pairs = [(rid, reaction_lookup.get(rid)) for rid in reaction_set.reaction_ids]
    pairs = [
        (rid, rxn)
        for rid, rxn in pairs
        if rxn is not None
        and rxn.parameters is not None
        and rxn.parameters.reaction_type == ReactionParameterType.LHHW
    ]
    if not pairs:
        return ""

    nterm = max(
        (len(rxn.parameters.adsorption.terms) for _, rxn in pairs if rxn.parameters.adsorption),
        default=0,
    )

    lines = [f"REACTIONS {reaction_set.id} GENERAL", f"    PARAM NTERM-ADS={nterm}"]

    # REAC-DATA (one per reaction)
    for rid, rxn in pairs:
        p = rxn.parameters
        reversible = p.reversible if p.reversible is not None else True
        attrs = [f"REAC-DATA {rid}"]
        if p.name:
            attrs.append(f"NAME={p.name}")
        attrs.append("REAC-CLASS=LHHW")
        attrs.append(f"PHASE={p.phase or 'V'}")
        attrs.append(f"CBASIS={p.conc_basis or 'PARTIALPRES'}")
        attrs.append(f"RBASIS={p.cat_basis or 'CAT-WT'}")
        attrs.append(f"REVERSIBLE={'YES' if reversible else 'NO'}")
        attrs.append(f"REV-METH={p.rev_method or 'USER-SPEC'}")
        attrs.append(f'PRES-UNIT="{p.pres_unit or "BAR"}"')
        lines.append("    " + " ".join(attrs))

    # RATE-CON (kinetic factor, one per reaction)
    for rid, rxn in pairs:
        kf = rxn.parameters.kinetic_factor
        parts = [
            f"RATE-CON {rid}",
            f"PRE-EXP={_format_value(kf.pre_exp)}",
            f"ACT-ENERGY={_format_value(kf.act_energy)} <{kf.act_energy_unit}>",
        ]
        if kf.t_ref is not None:
            t_ref = f"T-REF={_format_value(kf.t_ref)}"
            if kf.t_ref_unit:
                t_ref += f" <{kf.t_ref_unit}>"
            parts.append(t_ref)
        lines.append("    " + " ".join(parts))

    # STOIC (one per reaction)
    for rid, rxn in pairs:
        lines.extend(_wrap_slash_items(f"STOIC {rid} MIXED ", _format_stoichiometry_items(rxn)))

    # DFORCE-EXP / DFORCE-EXP-2 (one per reaction)
    for keyword, attr in (("DFORCE-EXP", "term1"), ("DFORCE-EXP-2", "term2")):
        for rid, rxn in pairs:
            term = getattr(rxn.parameters.driving_force, attr)
            items = [f"MIXED {comp} {_format_value(exp)}" for comp, exp in term.exponents.items()]
            lines.extend(_wrap_slash_items(f"{keyword} {rid} ", items))

    # DFORCE-EQ-1 / DFORCE-EQ-2 (grouped across reactions)
    for keyword, attr in (("DFORCE-EQ-1", "term1"), ("DFORCE-EQ-2", "term2")):
        items = [
            f"REACNO={rid} " + _format_coeff(getattr(rxn.parameters.driving_force, attr).coeff)
            for rid, rxn in pairs
        ]
        lines.extend(_wrap_slash_items(f"{keyword} ", items))

    # ADSORP-EXP (grouped: per reaction, per component)
    ads_exp_items = [
        f"REACNO={rid} CID={comp} SSID=MIXED EXPONENT="
        + " ".join(_format_value(x) for x in vector)
        for rid, rxn in pairs
        for comp, vector in rxn.parameters.adsorption.exponents.items()
    ]
    lines.extend(_wrap_slash_items("ADSORP-EXP ", ads_exp_items))

    # ADSORP-EQTER (grouped: per reaction, per term)
    eqter_items = [
        f"REACNO={rid} TERM={t} " + _format_coeff(term.coeff)
        for rid, rxn in pairs
        for t, term in enumerate(rxn.parameters.adsorption.terms, start=1)
    ]
    lines.extend(_wrap_slash_items("ADSORP-EQTER ", eqter_items))

    # ADSORP-POW (grouped)
    pow_items = [
        f"REACNO={rid} EXPONENT={_format_value(rxn.parameters.adsorption.power)}"
        for rid, rxn in pairs
    ]
    lines.extend(_wrap_slash_items("ADSORP-POW ", pow_items))

    return "\n".join(lines)


def _generate_comments(text: str) -> str:
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line:
            lines.append(f"; {line}")
        else:
            lines.append(";")
    return "\n".join(lines)


def validate_inp(content: str, return_report: bool = True) -> Union[Dict[str, Any], bool]:
    """
    Validate basic INP syntax and formatting. Returns a detailed report by default.
    """
    report: Dict[str, Any] = {"valid": True, "errors": []}

    def add_error(line_no: int, message: str, suggestion: str = "", section: str = "") -> None:
        location = f"{section}:line {line_no}" if section else f"line {line_no}"
        report["errors"].append(
            {
                "severity": "error",
                "line": line_no,
                "location": location,
                "message": message,
                "suggestion": suggestion,
            }
        )
        report["valid"] = False

    lines = content.splitlines()

    # Required section order validation
    found_sections: Dict[str, int] = {}
    for idx, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith(";"):
            continue
        if raw.startswith(" "):
            continue

        # Check against all known sections
        for key in ALL_SECTION_ORDER:
            if stripped.startswith(key) and key not in found_sections:
                found_sections[key] = idx

    # 1. Check for missing mandatory sections
    for key in REQUIRED_SECTION_ORDER:
        if key not in found_sections:
            add_error(0, f"Missing required section '{key}'", f"Add a {key} section")

    # 2. Check for out-of-order sections (mandatory AND optional)
    last_line = -1
    last_key = ""

    # We iterate through the expected order of ALL sections
    for key in ALL_SECTION_ORDER:
        line_no = found_sections.get(key)
        if line_no is None:
            continue

        if last_line != -1 and line_no < last_line:
            add_error(
                line_no,
                f"Section '{key}' is out of order (found after '{last_key}')",
                "Reorder sections to match Aspen requirements"
            )

        last_line = line_no
        last_key = key

    # Continuation character validation
    for idx, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith(";"):
            continue
        if "&" in raw:
            if not raw.rstrip().endswith("&"):
                add_error(idx, "Continuation character '&' must be at end of line", "Move '&' to end of the line")
                continue
            next_idx = idx
            while next_idx < len(lines):
                next_idx += 1
                if next_idx > len(lines):
                    break
                next_line = lines[next_idx - 1]
                if not next_line.strip() or next_line.lstrip().startswith(";"):
                    continue
                if not next_line.startswith(" "):
                    add_error(idx, "Continuation line must be indented", "Indent the continuation line")
                break

    # DATABANKS and PROP-SOURCES balanced quotes
    for section in ("DATABANKS", "PROP-SOURCES"):
        section_lines = _collect_section_lines(lines, section)
        if section_lines:
            quote_count = sum(line.count("'") for line in section_lines)
            if quote_count % 2 != 0:
                add_error(section_lines[0][0], f"Unbalanced quotes in {section}", "Ensure databank names are properly quoted")

    # COMPONENTS terminators
    component_lines = _collect_section_lines(lines, "COMPONENTS")
    if component_lines:
        # Filter out comments and empty lines to find the last actual component line
        real_component_lines = [
            (line_no, raw)
            for line_no, raw in component_lines
            if raw.strip() and not raw.strip().startswith(";") and not raw.strip().startswith("COMPONENTS")
        ]

        last_line_no = real_component_lines[-1][0] if real_component_lines else -1

        for line_no, raw in component_lines[1:]:
            stripped = raw.strip()
            if not stripped or stripped.startswith(";"):
                continue

            if not stripped.endswith("/"):
                # For the last line, we can be lenient or strictly enforce.
                is_last_line = (line_no == last_line_no)
                if not is_last_line:
                    add_error(line_no, "Component line missing '/' terminator", "Add '/' at end of component line", "COMPONENTS")
                else:
                     # Warn or ignore for the last line if sticking to MethanolPlant.inp canonical format
                     pass

    # STREAM sections
    stream_blocks = _collect_blocks(lines, "STREAM")
    for block in stream_blocks:
        header_line = block[0]
        block_lines = [entry[1] for entry in block]
        line_numbers = [entry[0] for entry in block]

        if not any(line.strip().startswith("SUBSTREAM") for line in block_lines):
            add_error(header_line[0], "STREAM section missing SUBSTREAM keyword", "Add a SUBSTREAM MIXED line", "STREAM")

        for line_index, (line_no, raw) in enumerate(block):
            stripped = raw.strip()
            if stripped in {"MASS-FRAC", "MOLE-FRAC"}:
                comp_entries: List[Tuple[int, str]] = []
                for follow_index in range(line_index + 1, len(block_lines)):
                    follow_raw = block_lines[follow_index]
                    follow_stripped = follow_raw.strip()
                    if not follow_stripped or follow_stripped.startswith(";"):
                        continue
                    if not follow_raw.startswith(" "):
                        break
                    if follow_stripped.startswith(tuple(TOP_LEVEL_KEYWORDS)):
                        break
                    comp_entries.append((line_numbers[follow_index], follow_raw))

                if not comp_entries:
                    add_error(
                        line_no,
                        "Composition sentence missing component/fraction pairs",
                        "Use MOLE-FRAC COMP VALUE / COMP VALUE syntax",
                        "STREAM",
                    )
                for entry_index, (entry_line_no, entry_raw) in enumerate(comp_entries):
                    entry = entry_raw.strip()
                    if not entry.endswith("/") and not entry.endswith("/ &"):
                        add_error(
                            entry_line_no,
                            "Composition line missing '/' terminator",
                            "Add '/' at end of composition line",
                            "STREAM",
                        )
                    if entry_index == len(comp_entries) - 1 and entry.endswith("&"):
                        add_error(
                            entry_line_no,
                            "Last composition line should not end with '&'",
                            "Remove '&' from the last composition line",
                            "STREAM",
                        )

    # BLOCK sections
    block_blocks = _collect_blocks(lines, "BLOCK", require_column_zero=True)
    for block in block_blocks:
        header = block[0][1]
        header_line_no = block[0][0]
        header_parts = header.split()
        block_type = header_parts[2].upper() if len(header_parts) > 2 else ""

        block_lines = [entry[1] for entry in block[1:]]
        if not block_lines:
            continue

        has_param = any(line.strip().startswith("PARAM") for line in block_lines)
        param_assignments = [line for line in block_lines if "=" in line and not line.strip().startswith("FRAC")]

        if block_type not in ("FSPLIT",):
            if param_assignments and not has_param:
                add_error(header_line_no, "PARAM keyword missing before parameter assignments", "Add a PARAM line before parameters", "BLOCK")

    return report if return_report else report["valid"]


def _collect_section_lines(lines: List[str], section: str) -> List[Tuple[int, str]]:
    indices = []
    start = None
    for idx, raw in enumerate(lines):
        if raw.startswith(section):
            start = idx
            break

    if start is None:
        return []

    indices.append((start + 1, lines[start]))
    for idx in range(start + 1, len(lines)):
        raw = lines[idx]
        stripped = raw.strip()
        if not stripped or stripped.startswith(";"):
            indices.append((idx + 1, raw))
            continue
        if raw.startswith(" "):
            indices.append((idx + 1, raw))
            continue
        if stripped.startswith(section):
            indices.append((idx + 1, raw))
            continue
        if stripped.startswith(tuple(TOP_LEVEL_KEYWORDS)):
            break
        indices.append((idx + 1, raw))

    return indices


def _collect_blocks(lines: List[str], header: str, require_column_zero: bool = False) -> List[List[Tuple[int, str]]]:
    blocks: List[List[Tuple[int, str]]] = []
    current: List[Tuple[int, str]] = []

    def is_header(raw: str) -> bool:
        if require_column_zero and raw.startswith(" "):
            return False
        return raw.strip().startswith(header)

    for idx, raw in enumerate(lines):
        if is_header(raw):
            if current:
                blocks.append(current)
            current = [(idx + 1, raw)]
            continue

        if current:
            stripped = raw.strip()
            if not stripped or stripped.startswith(";"):
                current.append((idx + 1, raw))
                continue
            if require_column_zero and raw.startswith(" "):
                current.append((idx + 1, raw))
                continue
            if stripped.startswith(tuple(TOP_LEVEL_KEYWORDS)) and not raw.startswith(" "):
                blocks.append(current)
                current = []
                continue
            current.append((idx + 1, raw))

    if current:
        blocks.append(current)

    return blocks
