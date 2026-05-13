import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from .exceptions import BuildError
from .schema import Block, FlowsheetConnection, PlantSpecification, Stream


logger = logging.getLogger("aspen_automation.com_builder")


TYPE_PATHS = (
    r"Input\TYPE",
    r"Input\MODEL",
    r"Input\MODELID",
    r"Input\MODEL_ID",
    r"Input\BLOCKTYPE",
    r"Input\OPTYPE",
)

STREAM_INPUT_PATHS = {
    "temperature": (r"Input\TEMP\MIXED", r"Input\TEMP"),
    "pressure": (r"Input\PRES\MIXED", r"Input\PRES"),
    "mass_flow": (r"Input\TOTFLOW\MIXED", r"Input\TOTFLOW"),
    "mole_flow": (r"Input\MOLEFLOW\MIXED", r"Input\MOLEFLOW"),
}

BLOCK_PORT_HINTS = {
    "MIXER": {
        "input": (r"Ports\F(IN)", r"Input\FEED", r"Connections\Inlet"),
        "output": (r"Ports\P(OUT)", r"Output\PROD", r"Connections\Outlet"),
    },
    "RGIBBS": {
        "input": (r"Ports\F(IN)", r"Input\FEED", r"Connections\Inlet"),
        "output": (r"Ports\P(OUT)", r"Output\PROD", r"Connections\Outlet"),
    },
    "HEATER": {
        "input": (r"Ports\F(IN)", r"Input\FEED", r"Connections\Inlet"),
        "output": (r"Ports\P(OUT)", r"Output\PROD", r"Connections\Outlet"),
    },
    "COMPR": {
        "input": (r"Ports\F(IN)", r"Input\FEED", r"Connections\Inlet"),
        "output": (r"Ports\P(OUT)", r"Output\PROD", r"Connections\Outlet"),
    },
    "REQUIL": {
        "input": (r"Ports\F(IN)", r"Input\FEED", r"Connections\Inlet"),
        "output": (r"Ports\P(OUT)", r"Output\PROD", r"Connections\Outlet"),
    },
    "RPLUG": {
        "input": (r"Ports\F(IN)", r"Input\FEED", r"Connections\Inlet"),
        "output": (r"Ports\P(OUT)", r"Output\PROD", r"Connections\Outlet"),
    },
    "RSTOIC": {
        "input": (r"Ports\F(IN)", r"Input\FEED", r"Connections\Inlet"),
        "output": (r"Ports\P(OUT)", r"Output\PROD", r"Connections\Outlet"),
    },
    "FLASH2": {
        "input": (r"Ports\F(IN)", r"Input\FEED", r"Connections\Inlet"),
        "output": (
            r"Ports\V(OUT)",
            r"Output\VAP",
            r"Connections\Vapor",
            r"Ports\L(OUT)",
            r"Output\LIQ",
            r"Connections\Liquid",
            r"Ports\P1(OUT)",
            r"Output\P1",
            r"Ports\P2(OUT)",
            r"Output\P2",
            r"Ports\P(OUT)",
            r"Output\PROD",
        ),
    },
    "FSPLIT": {
        "input": (r"Ports\F(IN)", r"Input\FEED", r"Connections\Inlet"),
        "output": (
            r"Ports\P1(OUT)",
            r"Output\P1",
            r"Ports\P2(OUT)",
            r"Output\P2",
            r"Ports\P(OUT)",
            r"Output\PROD",
        ),
    },
    "SEP": {
        "input": (r"Ports\F(IN)", r"Input\FEED", r"Connections\Inlet"),
        "output": (
            r"Ports\P1(OUT)",
            r"Output\P1",
            r"Ports\P2(OUT)",
            r"Output\P2",
            r"Ports\P(OUT)",
            r"Output\PROD",
        ),
    },
}

DEFAULT_BLOCK_PORT_HINTS = {
    "input": (r"Ports\F(IN)", r"Input\FEED", r"Connections\Inlet", r"Ports\F", r"Input\IN"),
    "output": (r"Ports\P(OUT)", r"Output\PROD", r"Connections\Outlet", r"Ports\P", r"Output\OUT"),
}


@dataclass
class BlockCreationStrategy:
    name: str
    type_field: str = ""


def infer_external_feed_streams(spec: Union[PlantSpecification, Dict[str, Any]]) -> List[str]:
    spec_obj = spec if isinstance(spec, PlantSpecification) else PlantSpecification(**spec)
    produced_streams = {
        stream_name.upper()
        for connection in spec_obj.flowsheet
        for stream_name in connection.outputs
    }
    feeds: List[str] = []
    for stream in spec_obj.streams:
        if stream.name.upper() not in produced_streams:
            feeds.append(stream.name)
    return feeds


def build_flowsheet_via_com(
    spec: Union[PlantSpecification, Dict[str, Any]],
    aspen: Any,
) -> Dict[str, Any]:
    spec_obj = spec if isinstance(spec, PlantSpecification) else PlantSpecification(**spec)
    diagnostics: Dict[str, Any] = {
        "build_mechanism": "com_block_builder",
        "components_added": [],
        "components_skipped": [],
        "streams_created": [],
        "streams_existing": [],
        "blocks_created": [],
        "blocks_existing": [],
        "connections_applied": [],
        "feed_streams": infer_external_feed_streams(spec_obj),
        "feed_inputs_configured": [],
        "block_parameters_applied": [],
        "block_parameter_warnings": [],
        "reaction_warnings": [],
    }

    try:
        _set_property_method(aspen, spec_obj, diagnostics)
        _ensure_components(aspen, spec_obj, diagnostics)
        _ensure_streams(aspen, spec_obj, diagnostics)
        strategy = _ensure_blocks(aspen, spec_obj, diagnostics)
        diagnostics["block_creation_strategy"] = {
            "name": strategy.name,
            "type_field": strategy.type_field,
        }
        _connect_flowsheet(aspen, spec_obj, diagnostics)
        _configure_feed_streams(aspen, spec_obj, diagnostics)
        _apply_block_configuration(aspen, spec_obj, diagnostics)
        verification = _verify_materialized_flowsheet(aspen)
        diagnostics["flowsheet_verification"] = verification
        diagnostics.update(verification)
    except BuildError:
        raise
    except Exception as exc:
        raise BuildError(
            f"COM block builder failed: {exc}",
            build_mode="auto",
            mechanism_tried="com_block_builder",
            diagnostics=diagnostics,
        ) from exc

    if not diagnostics.get("build_valid", False):
        raise BuildError(
            "COM block builder did not materialize a usable flowsheet.",
            build_mode="auto",
            mechanism_tried="com_block_builder",
            diagnostics=diagnostics,
        )

    return diagnostics


def _verify_materialized_flowsheet(aspen: Any) -> Dict[str, Any]:
    streams_node = _require_node(aspen.Tree.FindNode(r"\Data\Streams"), r"\Data\Streams")
    blocks_node = _require_node(aspen.Tree.FindNode(r"\Data\Blocks"), r"\Data\Blocks")

    stream_names = _element_names(streams_node)
    block_names = _element_names(blocks_node)
    build_valid = bool(stream_names) and bool(block_names)
    return {
        "build_valid": build_valid,
        "stream_count": len(stream_names),
        "block_count": len(block_names),
        "stream_samples": stream_names[:5],
        "block_samples": block_names[:5],
    }


def _set_property_method(aspen: Any, spec: PlantSpecification, diagnostics: Dict[str, Any]) -> None:
    method_node = _find_first_node(
        aspen.Tree,
        (
            r"\Data\Properties\Global\Input\METHOD",
            r"\Data\Properties\Specifications\Input\METHOD",
            r"\Data\Properties\Specifications\Input\GOPSETNAME",
        ),
    )
    if not method_node:
        properties_input = aspen.Tree.FindNode(r"\Data\Properties\Specifications\Input")
        if properties_input:
            for child in _element_objects(properties_input):
                name = _node_name(child).upper()
                if "METHOD" in name or "GOPSET" in name:
                    method_node = child
                    break
    method_node = _require_node(
        method_node,
        r"\Data\Properties\Specifications\Input\[METHOD|GOPSETNAME]",
    )
    method_node.Value = spec.properties.method
    diagnostics["property_method"] = spec.properties.method


def _ensure_components(aspen: Any, spec: PlantSpecification, diagnostics: Dict[str, Any]) -> None:
    comp_node = aspen.Tree.FindNode(r"\Data\Components\Specifications\Input\CAG_IDS")
    if not comp_node:
        comp_node = _require_node(
            aspen.Tree.FindNode(r"\Data\Components\Specifications"),
            r"\Data\Components\Specifications",
        )

    for component in spec.components:
        added = False
        for token in (component.id, component.name):
            if not token:
                continue
            try:
                comp_node.Elements.Add(token)
                diagnostics["components_added"].append(component.id)
                added = True
                break
            except Exception:
                continue
        if not added:
            diagnostics["components_skipped"].append(component.id)


def _ensure_streams(aspen: Any, spec: PlantSpecification, diagnostics: Dict[str, Any]) -> None:
    streams_node = _require_node(aspen.Tree.FindNode(r"\Data\Streams"), r"\Data\Streams")

    for stream in spec.streams:
        existing = aspen.Tree.FindNode(rf"\Data\Streams\{stream.name}")
        if existing:
            diagnostics["streams_existing"].append(stream.name)
            continue
        try:
            streams_node.Elements.Add(stream.name)
            diagnostics["streams_created"].append(stream.name)
        except Exception as exc:
            raise RuntimeError(f"Failed to create stream '{stream.name}': {exc}") from exc


def _ensure_blocks(
    aspen: Any,
    spec: PlantSpecification,
    diagnostics: Dict[str, Any],
) -> BlockCreationStrategy:
    strategy: Optional[BlockCreationStrategy] = None
    for block in spec.blocks:
        existing = aspen.Tree.FindNode(rf"\Data\Blocks\{block.name}")
        if existing:
            diagnostics["blocks_existing"].append(block.name)
            continue
        strategy = _create_block(aspen, block, diagnostics, strategy)
        diagnostics["blocks_created"].append(block.name)
    if strategy is None:
        return BlockCreationStrategy(name="elements_add")
    return strategy


def _create_block(
    aspen: Any,
    block: Block,
    diagnostics: Dict[str, Any],
    preferred_strategy: Optional[BlockCreationStrategy],
) -> BlockCreationStrategy:
    blocks_node = _require_node(aspen.Tree.FindNode(r"\Data\Blocks"), r"\Data\Blocks")
    candidates = _block_model_candidates(block.type)
    default_strategies = [
        BlockCreationStrategy(name="elements_add"),
        BlockCreationStrategy(name="newchild_set_type", type_field=TYPE_PATHS[0]),
        BlockCreationStrategy(name="pfs_select_model"),
        BlockCreationStrategy(name="pfs_dialogs_add"),
    ]
    strategies: List[BlockCreationStrategy] = []
    if preferred_strategy is not None:
        strategies.append(preferred_strategy)
    for candidate_strategy in default_strategies:
        if all(candidate_strategy.name != existing.name for existing in strategies):
            strategies.append(candidate_strategy)

    last_error: Optional[Exception] = None
    attempts: List[Dict[str, Any]] = []
    for strategy in strategies:
        for candidate in candidates:
            attempts.append({"strategy": strategy.name, "candidate": candidate})
            try:
                if strategy.name == "elements_add":
                    blocks_node.Elements.Add(block.name, candidate)
                    time.sleep(1.0)
                elif strategy.name == "newchild_set_type":
                    blocks_node.NewChild(block.name)
                    time.sleep(1.0)
                    block_node = _require_node(
                        aspen.Tree.FindNode(rf"\Data\Blocks\{block.name}"),
                        rf"\Data\Blocks\{block.name}",
                    )
                    type_node = _find_first_node(block_node, TYPE_PATHS)
                    if not type_node:
                        raise RuntimeError("No type field available after NewChild().")
                    type_node.Value = candidate
                    time.sleep(1.0)
                elif strategy.name == "pfs_select_model":
                    if not hasattr(blocks_node, "PFSSelectModel"):
                        raise RuntimeError("Blocks node has no PFSSelectModel method.")
                    blocks_node.PFSSelectModel(candidate)
                    time.sleep(1.0)
                    blocks_node.NewChild(block.name)
                    time.sleep(1.0)
                elif strategy.name == "pfs_dialogs_add":
                    dialogs = _dispatch_pfs_dialogs()
                    if dialogs is None:
                        raise RuntimeError("PFSFlowsheetDialogs COM object not available.")
                    before = set(_element_names(blocks_node))
                    dialogs.UnplacedBlocksDialogAddBlock(candidate)
                    time.sleep(2.0)
                    after = set(_element_names(blocks_node))
                    created_names = sorted(after - before)
                    if not created_names:
                        raise RuntimeError("No new block detected after PFS dialog add.")
                    created_name = created_names[0]
                    if created_name != block.name:
                        try:
                            blocks_node.RenameChild(created_name, block.name)
                        except Exception:
                            pass
                else:
                    raise RuntimeError(f"Unsupported block creation strategy '{strategy.name}'.")
                if _block_verified(aspen, block.name):
                    diagnostics.setdefault("block_creation_attempts", {})[block.name] = attempts
                    return strategy
            except Exception as exc:
                last_error = exc
            _remove_block(aspen, block.name)

    diagnostics.setdefault("block_creation_attempts", {})[block.name] = attempts
    raise RuntimeError(
        f"Unable to create block '{block.name}' as '{block.type}'. "
        f"Last error: {last_error}"
    )


def _connect_flowsheet(aspen: Any, spec: PlantSpecification, diagnostics: Dict[str, Any]) -> None:
    block_lookup = {block.name: block for block in spec.blocks}
    for connection in spec.flowsheet:
        block = block_lookup.get(connection.block)
        if block is None:
            raise RuntimeError(f"Flowsheet references unknown block '{connection.block}'.")

        block_node = _require_node(
            aspen.Tree.FindNode(rf"\Data\Blocks\{connection.block}"),
            rf"\Data\Blocks\{connection.block}",
        )

        input_nodes = _resolve_connection_nodes(block_node, block.type, "input")
        output_nodes = _resolve_connection_nodes(block_node, block.type, "output")
        if not input_nodes:
            raise RuntimeError(f"No input connection node found for block '{connection.block}'.")
        if not output_nodes:
            raise RuntimeError(f"No output connection node found for block '{connection.block}'.")

        _attach_streams_to_nodes(input_nodes, connection.inputs)
        output_assignment = _order_output_nodes(block.type, connection.outputs, output_nodes)
        _attach_streams_to_nodes(output_assignment, connection.outputs)

        diagnostics["connections_applied"].append(
            {
                "block": connection.block,
                "inputs": list(connection.inputs),
                "outputs": list(connection.outputs),
                "input_nodes": [_node_name(node) for node in input_nodes],
                "output_nodes": [_node_name(node) for node in output_assignment],
            }
        )


def _configure_feed_streams(aspen: Any, spec: PlantSpecification, diagnostics: Dict[str, Any]) -> None:
    feed_names = {name.upper() for name in diagnostics["feed_streams"]}
    for stream in spec.streams:
        if stream.name.upper() not in feed_names:
            continue
        stream_input = _require_node(
            aspen.Tree.FindNode(rf"\Data\Streams\{stream.name}\Input"),
            rf"\Data\Streams\{stream.name}\Input",
        )

        _set_first_value(stream_input, STREAM_INPUT_PATHS["temperature"], stream.temperature)
        _set_first_value(stream_input, STREAM_INPUT_PATHS["pressure"], stream.pressure)
        if stream.mass_flow is not None:
            _set_first_value(stream_input, STREAM_INPUT_PATHS["mass_flow"], stream.mass_flow)
            total_flow = stream.mass_flow
        else:
            _set_first_value(stream_input, STREAM_INPUT_PATHS["mole_flow"], stream.mole_flow)
            total_flow = stream.mole_flow

        component_flow_base = total_flow if total_flow is not None else 0.0
        for component, fraction in stream.composition.items():
            component_node = stream_input.FindNode(rf"FLOW\MIXED\{component}")
            if component_node:
                component_node.Value = component_flow_base * fraction
                continue
            fraction_node = stream_input.FindNode(rf"MOLEFRAC\MIXED\{component}")
            if fraction_node:
                fraction_node.Value = fraction

        diagnostics["feed_inputs_configured"].append(stream.name)


def _apply_block_configuration(aspen: Any, spec: PlantSpecification, diagnostics: Dict[str, Any]) -> None:
    for block in spec.blocks:
        block_node = _require_node(
            aspen.Tree.FindNode(rf"\Data\Blocks\{block.name}"),
            rf"\Data\Blocks\{block.name}",
        )

        for key, value in (block.parameters or {}).items():
            applied = _set_block_input_value(block_node, key, value)
            diagnostics["block_parameters_applied"].append(
                {"block": block.name, "parameter": key, "value": value, "applied": applied}
            )
            if not applied:
                diagnostics["block_parameter_warnings"].append(
                    f"Could not set parameter '{key}' on block '{block.name}'."
                )

        if block.split_fractions:
            for fraction in block.split_fractions:
                if not _set_split_fraction(block_node, fraction.stream, fraction.fraction):
                    diagnostics["block_parameter_warnings"].append(
                        f"Could not set split fraction for '{block.name}' stream '{fraction.stream}'."
                    )

        if block.sep_fractions:
            for fraction in block.sep_fractions:
                if not _set_sep_fraction(
                    block_node,
                    fraction.stream,
                    fraction.substream,
                    fraction.component,
                    fraction.fraction,
                ):
                    diagnostics["block_parameter_warnings"].append(
                        "Could not set SEP fraction "
                        f"for block '{block.name}', stream '{fraction.stream}', component '{fraction.component}'."
                    )

        if block.reactions:
            diagnostics["reaction_warnings"].append(
                f"Reaction-set attachment for block '{block.name}' is not automated yet; "
                f"requested reaction set '{block.reactions}' was left for Aspen defaults."
            )


def _block_model_candidates(model: str) -> List[str]:
    tokens = [model, model.upper(), model.title(), model.lower()]
    unique: List[str] = []
    for token in tokens:
        if token and token not in unique:
            unique.append(token)
    return unique


def _block_verified(aspen: Any, block_name: str) -> bool:
    block_node = aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}")
    if not block_node:
        return False
    return bool(block_node.FindNode("Ports") or block_node.FindNode("Input") or block_node.FindNode("Output"))


def _remove_block(aspen: Any, block_name: str) -> None:
    try:
        blocks_node = aspen.Tree.FindNode(r"\Data\Blocks")
        if blocks_node:
            blocks_node.Elements.Remove(block_name)
    except Exception:
        pass


def _dispatch_pfs_dialogs() -> Optional[Any]:
    try:
        import win32com.client as win32
    except Exception:
        return None

    for prog_id in (
        "AspenTech.AspenPlus.PfsDialogs.PFSFlowsheetDialogs.400",
        "AspenTech.AspenPlus.PfsDialogs.PFSFlowsheetDialogs.40.0",
    ):
        try:
            return win32.Dispatch(prog_id)
        except Exception:
            continue
    return None


def _resolve_connection_nodes(block_node: Any, block_type: str, direction: str) -> List[Any]:
    hints = BLOCK_PORT_HINTS.get(block_type.upper(), DEFAULT_BLOCK_PORT_HINTS)
    nodes: List[Any] = []
    seen_paths = set()
    for path in hints[direction]:
        if path in seen_paths:
            continue
        seen_paths.add(path)
        node = block_node.FindNode(path)
        if node:
            nodes.append(node)

    if nodes:
        return nodes

    search_terms = ("IN", "FEED", "VAP", "LIQ", "OUT", "PROD", "P1", "P2")
    for section_name in ("Ports", "Input", "Output", "Connections"):
        section = block_node.FindNode(section_name)
        if not section:
            continue
        for child in _element_objects(section):
            name = _node_name(child).upper()
            if direction == "input" and ("IN" in name or "FEED" in name):
                nodes.append(child)
            elif direction == "output" and any(term in name for term in search_terms if term != "IN"):
                nodes.append(child)
    return nodes


def _attach_streams_to_nodes(nodes: Sequence[Any], stream_names: Sequence[str]) -> None:
    if not nodes or not stream_names:
        return
    if len(nodes) == 1:
        for stream_name in stream_names:
            nodes[0].Elements.Add(stream_name)
        return
    for node, stream_name in zip(nodes, stream_names):
        node.Elements.Add(stream_name)


def _order_output_nodes(block_type: str, stream_names: Sequence[str], nodes: Sequence[Any]) -> List[Any]:
    if len(nodes) <= 1 or len(stream_names) <= 1:
        return list(nodes)

    remaining = list(nodes)
    ordered: List[Any] = []
    for stream_name in stream_names:
        preferred = _select_best_output_node(stream_name, remaining, block_type)
        ordered.append(preferred)
        remaining.remove(preferred)
        if not remaining:
            break
    ordered.extend(remaining)
    return ordered


def _select_best_output_node(stream_name: str, nodes: Sequence[Any], block_type: str) -> Any:
    stream_key = stream_name.upper()
    block_key = block_type.upper()
    if block_key == "FLASH2":
        if any(token in stream_key for token in ("GAS", "VAP", "PURGE")):
            for node in nodes:
                name = _node_name(node).upper()
                if "V" in name or "VAP" in name or "P1" in name:
                    return node
        if any(token in stream_key for token in ("WATER", "LIQ", "CRUDE", "MEOH")):
            for node in nodes:
                name = _node_name(node).upper()
                if "L" in name or "LIQ" in name or "P2" in name:
                    return node
    return nodes[0]


def _set_block_input_value(block_node: Any, key: str, value: Any) -> bool:
    direct_paths = (
        rf"Input\{key}",
        rf"Input\{key}\1",
        rf"Input\OPERATING\{key}",
        rf"Input\PARAM\{key}",
    )
    node = _find_first_node(block_node, direct_paths)
    if node:
        node.Value = value
        return True

    input_node = block_node.FindNode("Input")
    if not input_node:
        return False
    key_upper = key.upper()
    for child in _element_objects(input_node):
        if _node_name(child).upper() == key_upper:
            child.Value = value
            return True
    return False


def _set_split_fraction(block_node: Any, stream_name: str, fraction: float) -> bool:
    paths = (
        rf"Input\FRAC\{stream_name}",
        rf"Input\SPLIT\{stream_name}",
        rf"Input\{stream_name}",
    )
    node = _find_first_node(block_node, paths)
    if node:
        node.Value = fraction
        return True
    return False


def _set_sep_fraction(
    block_node: Any,
    stream_name: str,
    substream: str,
    component: str,
    fraction: float,
) -> bool:
    paths = (
        rf"Input\FRAC\{stream_name}\{substream}\{component}",
        rf"Input\FRAC\{stream_name}\{component}",
        rf"Input\{stream_name}\{component}",
    )
    node = _find_first_node(block_node, paths)
    if node:
        node.Value = fraction
        return True
    return False


def _set_first_value(base_node: Any, paths: Sequence[str], value: Any) -> None:
    node = _find_first_node(base_node, paths)
    if not node:
        raise RuntimeError(f"Could not find a writable node under '{_node_name(base_node)}' for paths {paths}.")
    node.Value = value


def _find_first_node(base_node: Any, paths: Iterable[str]) -> Optional[Any]:
    for path in paths:
        try:
            node = base_node.FindNode(path)
        except Exception:
            node = None
        if node:
            return node
    return None


def _require_node(node: Any, path: str) -> Any:
    if node is None:
        raise RuntimeError(f"Required Aspen tree node '{path}' was not found.")
    return node


def _element_names(node: Any) -> List[str]:
    return [_node_name(child) for child in _element_objects(node)]


def _element_objects(node: Any) -> List[Any]:
    elements = getattr(node, "Elements", None)
    if elements is None:
        return []
    try:
        count = int(elements.Count)
    except Exception:
        return []

    items: List[Any] = []
    for raw_index in range(count):
        item = None
        for candidate_index in (raw_index, raw_index + 1):
            try:
                item = elements.Item(candidate_index)
                break
            except Exception:
                continue
        if item is not None:
            items.append(item)
    return items


def _node_name(node: Any) -> str:
    try:
        name = getattr(node, "Name")
    except Exception:
        return ""
    return "" if name is None else str(name)
