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
    Properties,
    Reaction,
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
    "FLOWSHEETING-OPTIONS",
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
    "FLOWSHEETING-OPTIONS",
    "FLOWSHEET",
    "STREAM",
    "BLOCK",
]

OPTIONAL_SECTION_ORDER = [
    "FLOWSHEETING-OPTIONS",
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
    "FLOWSHEETING-OPTIONS",
    "FLOWSHEET",
    "STREAM",
    "BLOCK",
    "CHEMISTRY",
    "REACTIONS",
]


def generate_inp(spec: Union[PlantSpecification, Dict[str, Any]], output_path: Optional[str] = None) -> str:
    """
    Generates an Aspen Plus .inp file based on the PlantSpecification.
    """
    spec_obj = _ensure_spec(spec)

    is_flowsheet_empty = not spec_obj.streams and not spec_obj.blocks
    if not spec_obj.streams:
        raise ValidationError("Spec must contain at least one stream", {"valid": False, "errors": [{"severity": "error", "message": "Spec must contain at least one stream"}]})
    if not spec_obj.blocks:
        raise ValidationError("Spec must contain at least one block", {"valid": False, "errors": [{"severity": "error", "message": "Spec must contain at least one block"}]})

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


    # 7. FLOWSHEETING OPTIONS (Omit as it causes ITSORT.1 in V14)
    # sections.append(_generate_flowsheeting_options(spec_obj.flowsheeting_options))

    # 8. FLOWSHEET
    sections.append(_generate_flowsheet(spec_obj.flowsheet))

    # 9. STREAM
    for stream in spec_obj.streams:
        sections.append(_generate_stream(stream))

    # 10. BLOCK
    for block in spec_obj.blocks:
        sections.append(_generate_block(block))

    # 11. CHEMISTRY (Optional)
    # Removed for RGIBBS stability
    
    # 12. REACTIONS (Optional)
    # Removed for RGIBBS stability

    inp_content = "\n\n".join(sections)

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
    db_list = props.databanks if props.databanks else [
        'APV140 PURE32', 'APV140 AQUEOUS', 'APV140 SOLIDS', 
        'APV140 INORGANIC'
    ]
    
    # Ensure NOASPENPCD is at the end if not present
    if not any("NOASPENPCD" in db.upper() for db in db_list):
        db_list.append("NOASPENPCD")
    
    quoted = [_quote_databank(db) for db in db_list]

    # Filter out NOASPENPCD and other non-sources from PROP-SOURCES
    prop_sources = [db for db in quoted if "NOASPENPCD" not in db.upper()]

    databank_lines = _format_continuation_section("DATABANKS", quoted)
    prop_lines = _format_continuation_section("PROP-SOURCES", prop_sources)

    return ["\n".join(databank_lines), "\n".join(prop_lines)]


def _generate_flowsheeting_options(options: Optional[Any]) -> str:
    # Default behavior if options is None
    mass_bal = "YES"
    energy_bal = "YES"
    
    if options:
        mass_bal = "YES" if options.mass_balance else "NO"
        energy_bal = "YES" if options.energy_balance else "NO"

    return ""  # Omitted for V14 stability



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
        # Use simpler one-pair-per-line format which is more robust in V14
        comp_type = "MOLE-FRAC"
        for comp_id, val in comp_items:
            lines.append(f"    {comp_type} {comp_id} {_format_value(val)}")

    return "\n".join(lines)


def _generate_block(block: Block) -> str:
    block_type = block.type.upper()
    if block_type == "REQUIL":
        block_type = "RGIBBS"

    lines = [f"BLOCK {block.name} {block_type}"]

    if block_type == "FSPLIT":
        lines.extend(_generate_fsplit_block(block))
        return "\n".join(lines)

    if block_type == "SEP":
        lines.extend(_generate_sep_block(block))
        return "\n".join(lines)

    if block.parameters:
        mapped_params = {}
        for k, v in block.parameters.items():
            if block_type == "COMPR" and k.upper() == "EFF":
                mapped_params["SEFF"] = v
            else:
                mapped_params[k.upper()] = v
        param_str = " ".join([f"{k}={_format_value(v)}" for k, v in mapped_params.items()])
        lines.append(f"    PARAM {param_str}")

    if block.reactions and block_type != "RGIBBS":
        pass  # Removed for RGIBBS stability

    return "\n".join(lines)


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
        param_str = " ".join([f"{k.upper()}={_format_value(v)}" for k, v in block.parameters.items()])
        lines.append(f"    PARAM {param_str}")

    if block.sep_fractions:
        for frac in block.sep_fractions:
            # Standard SEP syntax for V14: FRAC STRM=<outlet> COMP=<comp> FRAC=<fraction>
            # Avoid positional notation to prevent 'too many items' or 'unknown keyword' errors.
            lines.append(f"    FRAC STRM={frac.stream} COMP={frac.component} FRAC={_format_value(frac.fraction)}")

    if block.reactions:
        lines.append(f"    REACTIONS {block.reactions}")

    return lines


def _generate_chemistry(chem: Chemistry) -> str:
    lines = [f"CHEMISTRY {chem.id}"]
    for reaction in chem.reactions:
        lines.append(f"    STOIC {reaction.id} &")
        stoich_items = list(reaction.stoichiometry)
        for i, s in enumerate(stoich_items):
            terminator = " /" if i == len(stoich_items) - 1 else " / &"
            lines.append(f"        {s.component} {_format_value(s.coefficient)}{terminator}")
    return "\n".join(lines)


def _generate_reac_data_line(rxn_id: int, params: Optional[ReactionParameters]) -> str:
    # Just default REAC-DATA ID to avoid V14 model-match errors
    return f"    REAC-DATA {rxn_id}"

def _generate_reactions(reaction_set: ReactionSet, reaction_lookup: Dict[int, Reaction]) -> str:
    block_type = "EQUIL" if reaction_set.block_type == "REQUIL" else reaction_set.block_type
    lines = [f"REACTIONS {reaction_set.id} {block_type}"]
    for rxn_id in reaction_set.reaction_ids:
        reaction = reaction_lookup.get(rxn_id)
        params = reaction.parameters if reaction else None
        lines.append(_generate_reac_data_line(rxn_id, params))
        lines.extend(_generate_reaction_parameter_lines(rxn_id, params))
    return "\n".join(lines)


    return " ".join(tokens)


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

        comp_start_idx = None
        for i, raw in enumerate(block_lines):
            stripped = raw.strip()
            if stripped.startswith("MASS-FRAC") or stripped.startswith("MOLE-FRAC"):
                comp_start_idx = i
                break

        if comp_start_idx is not None:
            comp_entries: List[Tuple[int, str]] = []
            for j in range(comp_start_idx + 1, len(block_lines)):
                raw = block_lines[j]
                stripped = raw.strip()
                if not stripped or stripped.startswith(";"):
                    continue
                if not raw.startswith(" "):
                    break
                comp_entries.append((line_numbers[j], raw))

            if comp_entries:
                for k, (line_no, raw) in enumerate(comp_entries):
                    stripped = raw.strip()
                    if not stripped.endswith("/") and not stripped.endswith("/ &"):
                        add_error(line_no, "Composition line missing '/' terminator", "Add '/' at end of composition line", "STREAM")
                    if k == len(comp_entries) - 1 and stripped.endswith("&"):
                        add_error(line_no, "Last composition line should not end with '&'", "Remove '&' from the last composition line", "STREAM")

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
