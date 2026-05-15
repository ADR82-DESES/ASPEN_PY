import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import win32com.client as win32

try:
    import pywintypes
except Exception:  # pragma: no cover - best effort for COM error details
    pywintypes = None


PROJECT_DIR = Path(__file__).resolve().parent
ROOT_DIR = PROJECT_DIR.parent
LOG_DIR = ROOT_DIR / "logs"
LOG_PATH = LOG_DIR / "com_block_probe_log.txt"


TARGET_BLOCKS = [
    ("MIX-FEED", "MIXER"),
    ("B-ATR", "RGIBBS"),
    ("B-COOL", "HEATER"),
    ("B-FLASH", "FLASH2"),
    ("B-COMP", "COMPR"),
    ("MIX-LOOP", "MIXER"),
    ("B-SYN", "REQUIL"),
    ("B-SEP", "FLASH2"),
    ("SPLIT", "FSPLIT"),
    ("B-DIST", "SEP"),
]


ATTRIBUTE_CANDIDATES = [
    "MODEL",
    "TYPE",
    "MODELID",
    "MODEL_ID",
    "LIBRARY",
    "LIB",
    "LIBNAME",
    "LIBREF",
    "CLASS",
    "CATEGORY",
]

TYPE_PATHS = [
    r"Input\TYPE",
    r"Input\MODEL",
    r"Input\MODELID",
    r"Input\MODEL_ID",
    r"Input\BLOCKTYPE",
    r"Input\OPTYPE",
]


@dataclass
class ProbeResult:
    success: bool
    strategy: str = ""
    model_spec: str = ""
    type_field: str = ""
    created_name: str = ""
    notes: str = ""


class Logger:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(path, "w", encoding="utf-8")

    def log(self, msg: str) -> None:
        print(msg)
        self._file.write(msg + "\n")
        self._file.flush()

    def close(self) -> None:
        try:
            self._file.close()
        except Exception:
            pass


def format_com_error(err: Exception) -> str:
    if pywintypes and isinstance(err, pywintypes.com_error):
        hresult = getattr(err, "hresult", None)
        excepinfo = getattr(err, "excepinfo", None)
        details = ""
        if excepinfo:
            details = f" | excepinfo={excepinfo}"
        return f"COM error hresult={hresult}{details}"
    return str(err)


def connect_aspen(prefer_new: bool, logger: Logger):
    if not prefer_new:
        try:
            aspen = win32.GetActiveObject("Apwn.Document")
            logger.log("Connected to running Aspen Plus instance.")
            return aspen, True
        except Exception as err:
            logger.log(f"No running instance found: {format_com_error(err)}")

    aspen = win32.Dispatch("Apwn.Document")
    logger.log("Created new Aspen Plus instance via Dispatch.")
    return aspen, False


def ensure_initialized(aspen, logger: Logger) -> None:
    try:
        _ = aspen.Tree
    except Exception:
        logger.log("Initializing Aspen Plus with InitNew()...")
        aspen.InitNew()
        time.sleep(2)


def try_open_reference_case(aspen, logger: Logger) -> str:
    candidates = [
        PROJECT_DIR / "MethanolPlant.bkp",
        ROOT_DIR / "AutomatedMixer.bkp",
    ]
    for path in candidates:
        if path.exists():
            logger.log(f"Opening reference case: {path}")
            try:
                aspen.InitFromArchive2(str(path))
                time.sleep(2)
                return str(path)
            except Exception as err:
                logger.log(f"Failed to open {path}: {format_com_error(err)}")
    logger.log("No reference case found for metadata discovery.")
    return ""


def read_node_value(node) -> str:
    try:
        val = node.Value
        if val is None:
            return ""
        return str(val).strip()
    except Exception:
        return ""


def collect_block_metadata(aspen, logger: Logger) -> dict:
    blocks_node = aspen.Tree.FindNode(r"\Data\Blocks")
    if not blocks_node:
        logger.log("Blocks node not found; cannot collect metadata.")
        return {}

    metadata = {}
    try:
        count = blocks_node.Elements.Count
    except Exception:
        count = 0

    logger.log(f"Found {count} blocks in reference case.")
    for i in range(count):
        try:
            block_name = blocks_node.Elements.Item(i).Name
        except Exception:
            continue
        block_node = aspen.Tree.FindNode(rf"\Data\Blocks\{block_name}")
        if not block_node:
            continue

        info = {
            "name": block_name,
            "type_values": {},
            "class_attributes": {},
            "print_useful": "",
        }

        for path in TYPE_PATHS:
            try:
                node = block_node.FindNode(path)
                if node:
                    val = read_node_value(node)
                    if val:
                        info["type_values"][path] = val
            except Exception:
                continue

        for attr in ATTRIBUTE_CANDIDATES:
            try:
                val = block_node.ClassAttributeValue(attr)
                if val is not None:
                    val = str(val).strip()
                    if val:
                        info["class_attributes"][attr] = val
            except Exception:
                pass
            try:
                val = block_node.AttributeValue(attr)
                if val is not None:
                    val = str(val).strip()
                    if val:
                        info["class_attributes"][f"ATTR_{attr}"] = val
            except Exception:
                pass

        try:
            printable = block_node.PrintUseful()
            if printable:
                info["print_useful"] = str(printable)[:4000]
        except Exception:
            pass

        metadata[block_name] = info

    return metadata


def build_candidate_models(metadata: dict) -> list:
    candidates = set()

    # From target list
    for _, model in TARGET_BLOCKS:
        candidates.add(model)
        candidates.add(model.upper())
        candidates.add(model.lower())
        candidates.add(model.title())

    # From metadata
    for block_info in metadata.values():
        for val in block_info.get("type_values", {}).values():
            if val:
                candidates.add(val)
        for val in block_info.get("class_attributes", {}).values():
            if val:
                candidates.add(val)

    # Combine library and model if both were discovered
    libs = []
    models = []
    for block_info in metadata.values():
        for key, val in block_info.get("class_attributes", {}).items():
            if "LIB" in key.upper():
                libs.append(val)
            if "MODEL" in key.upper() or "TYPE" in key.upper():
                models.append(val)
    for lib in libs:
        for model in models:
            candidates.add(f"{lib}:{model}")
            candidates.add(f"{lib}.{model}")
            candidates.add(f"{lib}\\{model}")
            candidates.add(f"{lib} {model}")

    # Clean
    cleaned = []
    for c in candidates:
        c = str(c).strip()
        if not c:
            continue
        if c not in cleaned:
            cleaned.append(c)
    return cleaned


def list_blocks(aspen) -> list:
    blocks_node = aspen.Tree.FindNode(r"\Data\Blocks")
    if not blocks_node:
        return []
    names = []
    try:
        count = blocks_node.Elements.Count
        for i in range(count):
            try:
                names.append(blocks_node.Elements.Item(i).Name)
            except Exception:
                continue
    except Exception:
        pass
    return names


def remove_block(aspen, name: str, logger: Logger) -> None:
    try:
        blocks_node = aspen.Tree.FindNode(r"\Data\Blocks")
        if blocks_node:
            blocks_node.Elements.Remove(name)
            logger.log(f"Removed block '{name}'.")
    except Exception:
        pass


def get_block_type_value(block_node) -> str:
    for path in TYPE_PATHS:
        try:
            node = block_node.FindNode(path)
            if node:
                val = read_node_value(node)
                if val:
                    return val
        except Exception:
            continue
    for attr in ATTRIBUTE_CANDIDATES:
        try:
            val = block_node.ClassAttributeValue(attr)
            if val is not None:
                val = str(val).strip()
                if val:
                    return val
        except Exception:
            pass
    return ""


def verify_block(aspen, name: str, logger: Logger) -> bool:
    block_node = aspen.Tree.FindNode(rf"\Data\Blocks\{name}")
    if not block_node:
        logger.log(f"Verify failed: block '{name}' not found.")
        return False

    ports_node = block_node.FindNode("Ports")
    if not ports_node:
        logger.log(f"Verify failed: block '{name}' has no Ports node.")
        return False

    block_type = get_block_type_value(block_node)
    if not block_type:
        logger.log(f"Verify failed: block '{name}' has no model/type indicator.")
        return False

    logger.log(f"Verify success: '{name}' type/model='{block_type}'.")
    return True


def attempt_elements_add(aspen, blocks_node, name: str, candidates: list, logger: Logger) -> ProbeResult:
    for model in candidates:
        logger.log(f"[Elements.Add] Trying model '{model}'...")
        try:
            blocks_node.Elements.Add(name, model)
            time.sleep(1)
            if verify_block(aspen, name, logger):
                return ProbeResult(True, strategy="elements_add", model_spec=model, created_name=name)
        except Exception as err:
            logger.log(f"[Elements.Add] Failed for '{model}': {format_com_error(err)}")
        remove_block(aspen, name, logger)
    return ProbeResult(False)


def attempt_newchild_set_type(aspen, blocks_node, name: str, candidates: list, logger: Logger) -> ProbeResult:
    for model in candidates:
        logger.log(f"[NewChild+Set] Trying model '{model}'...")
        try:
            blocks_node.NewChild(name)
        except Exception as err:
            logger.log(f"[NewChild] Failed: {format_com_error(err)}")
            remove_block(aspen, name, logger)
            continue

        block_node = aspen.Tree.FindNode(rf"\Data\Blocks\{name}")
        if not block_node:
            remove_block(aspen, name, logger)
            continue

        for field in TYPE_PATHS:
            try:
                node = block_node.FindNode(field)
                if node:
                    node.Value = model
                    time.sleep(1)
                    if verify_block(aspen, name, logger):
                        return ProbeResult(
                            True,
                            strategy="newchild_set_type",
                            model_spec=model,
                            type_field=field,
                            created_name=name,
                        )
            except Exception as err:
                logger.log(f"[NewChild+Set] Field {field} failed: {format_com_error(err)}")

        remove_block(aspen, name, logger)
    return ProbeResult(False)


def attempt_pfs_select_model(aspen, blocks_node, name: str, candidates: list, logger: Logger) -> ProbeResult:
    if not hasattr(blocks_node, "PFSSelectModel"):
        logger.log("[PFSSelectModel] Not available on Blocks node.")
        return ProbeResult(False)

    for model in candidates:
        logger.log(f"[PFSSelectModel] Trying model '{model}'...")
        try:
            blocks_node.PFSSelectModel(model)
            time.sleep(1)
            blocks_node.NewChild(name)
            time.sleep(1)
            if verify_block(aspen, name, logger):
                return ProbeResult(True, strategy="pfs_select_model", model_spec=model, created_name=name)
        except Exception as err:
            logger.log(f"[PFSSelectModel] Failed for '{model}': {format_com_error(err)}")
        remove_block(aspen, name, logger)

    return ProbeResult(False)


def attempt_pfs_dialogs(aspen, name: str, candidates: list, logger: Logger) -> ProbeResult:
    dialog_prog_ids = [
        "AspenTech.AspenPlus.PfsDialogs.PFSFlowsheetDialogs.400",
        "AspenTech.AspenPlus.PfsDialogs.PFSFlowsheetDialogs.40.0",
    ]
    dialogs = None
    for prog_id in dialog_prog_ids:
        try:
            dialogs = win32.Dispatch(prog_id)
            logger.log(f"[PFSDialogs] Using ProgID: {prog_id}")
            break
        except Exception as err:
            logger.log(f"[PFSDialogs] Failed to load {prog_id}: {format_com_error(err)}")

    if not dialogs:
        logger.log("[PFSDialogs] Dialog COM object unavailable.")
        return ProbeResult(False)

    for model in candidates:
        logger.log(f"[PFSDialogs] Trying model '{model}'...")
        before = set(list_blocks(aspen))
        try:
            dialogs.UnplacedBlocksDialogAddBlock(model)
            time.sleep(2)
        except Exception as err:
            logger.log(f"[PFSDialogs] Failed for '{model}': {format_com_error(err)}")
            continue

        after = set(list_blocks(aspen))
        new_blocks = list(after - before)
        if not new_blocks:
            logger.log("[PFSDialogs] No new block detected.")
            continue

        created = new_blocks[0]
        if created != name:
            try:
                blocks_node = aspen.Tree.FindNode(r"\Data\Blocks")
                blocks_node.RenameChild(created, name)
                created = name
            except Exception as err:
                logger.log(f"[PFSDialogs] Rename failed: {format_com_error(err)}")
                created = new_blocks[0]

        if verify_block(aspen, created, logger):
            return ProbeResult(True, strategy="pfs_dialogs_add", model_spec=model, created_name=created)

        remove_block(aspen, created, logger)

    return ProbeResult(False)


def run_probe() -> ProbeResult:
    logger = Logger(LOG_PATH)
    logger.log("=" * 70)
    logger.log("COM-ONLY BLOCK CREATION PROBE")
    logger.log("=" * 70)

    aspen, _ = connect_aspen(prefer_new=True, logger=logger)
    ensure_initialized(aspen, logger)
    aspen.SuppressDialogs = 1
    aspen.Visible = True

    # Baseline discovery
    ref_path = try_open_reference_case(aspen, logger)
    metadata = {}
    if ref_path:
        try:
            metadata = collect_block_metadata(aspen, logger)
        except Exception as err:
            logger.log(f"Metadata discovery failed: {format_com_error(err)}")

    candidates = build_candidate_models(metadata)
    logger.log(f"Candidate model specs ({len(candidates)}):")
    for c in candidates:
        logger.log(f"  - {c}")

    # Start new blank case for the probe
    try:
        logger.log("Initializing new blank case for probe...")
        aspen.InitNew()
        time.sleep(2)
    except Exception as err:
        logger.log(f"InitNew failed: {format_com_error(err)}")
        logger.close()
        return ProbeResult(False, notes="InitNew failed")

    blocks_node = aspen.Tree.FindNode(r"\Data\Blocks")
    if not blocks_node:
        logger.log("Blocks node not found after InitNew.")
        logger.close()
        return ProbeResult(False, notes="Blocks node missing")

    test_name = "MIX-FEED"
    remove_block(aspen, test_name, logger)

    # Strategy 1
    result = attempt_elements_add(aspen, blocks_node, test_name, candidates, logger)
    if result.success:
        logger.log("Probe success with Elements.Add.")
        logger.close()
        return result

    # Strategy 2
    result = attempt_newchild_set_type(aspen, blocks_node, test_name, candidates, logger)
    if result.success:
        logger.log("Probe success with NewChild + set type.")
        logger.close()
        return result

    # Strategy 3
    result = attempt_pfs_select_model(aspen, blocks_node, test_name, candidates, logger)
    if result.success:
        logger.log("Probe success with PFSSelectModel.")
        logger.close()
        return result

    # Strategy 4
    result = attempt_pfs_dialogs(aspen, test_name, candidates, logger)
    if result.success:
        logger.log("Probe success with PFSFlowsheetDialogs.")
        logger.close()
        return result

    logger.log("COM-only block creation not supported in Aspen Plus 40.x (probe failed).")
    logger.close()
    return ProbeResult(False, notes="All strategies failed")


def main() -> int:
    result = run_probe()
    if result.success:
        print("PROBE SUCCESS")
        print(json.dumps(result.__dict__, indent=2))
        return 0

    print("PROBE FAILED")
    print(result.notes)
    return 1


if __name__ == "__main__":
    sys.exit(main())
