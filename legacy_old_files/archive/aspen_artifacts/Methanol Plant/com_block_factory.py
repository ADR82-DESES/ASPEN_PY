import time
from dataclasses import dataclass
from typing import Optional

import win32com.client as win32


TYPE_PATHS = [
    r"Input\TYPE",
    r"Input\MODEL",
    r"Input\MODELID",
    r"Input\MODEL_ID",
    r"Input\BLOCKTYPE",
    r"Input\OPTYPE",
]


@dataclass
class BlockCreationStrategy:
    name: str
    type_field: str = ""


def _find_block_node(aspen, name: str):
    return aspen.Tree.FindNode(rf"\Data\Blocks\{name}")


def _verify_block(aspen, name: str) -> bool:
    block_node = _find_block_node(aspen, name)
    if not block_node:
        return False
    if not block_node.FindNode("Ports"):
        return False
    # Verify some type/model indicator
    for path in TYPE_PATHS:
        try:
            node = block_node.FindNode(path)
            if node and node.Value:
                return True
        except Exception:
            continue
    return False


def _ensure_blocks_node(aspen):
    return aspen.Tree.FindNode(r"\Data\Blocks")


def create_block(aspen, name: str, model: str, strategy: BlockCreationStrategy, logger=None) -> None:
    blocks_node = _ensure_blocks_node(aspen)
    if not blocks_node:
        raise RuntimeError("Blocks node not available in Aspen tree.")

    if _find_block_node(aspen, name):
        if logger:
            logger.log(f"Block '{name}' already exists. Skipping.")
        return

    if strategy.name == "elements_add":
        blocks_node.Elements.Add(name, model)
        time.sleep(1)
    elif strategy.name == "newchild_set_type":
        blocks_node.NewChild(name)
        block_node = _find_block_node(aspen, name)
        if not block_node:
            raise RuntimeError(f"Block '{name}' not found after NewChild.")
        field = strategy.type_field or TYPE_PATHS[0]
        node = block_node.FindNode(field)
        if node:
            node.Value = model
        time.sleep(1)
    elif strategy.name == "pfs_select_model":
        if not hasattr(blocks_node, "PFSSelectModel"):
            raise RuntimeError("Blocks node has no PFSSelectModel method.")
        blocks_node.PFSSelectModel(model)
        time.sleep(1)
        blocks_node.NewChild(name)
        time.sleep(1)
    elif strategy.name == "pfs_dialogs_add":
        dialogs = None
        for prog_id in [
            "AspenTech.AspenPlus.PfsDialogs.PFSFlowsheetDialogs.400",
            "AspenTech.AspenPlus.PfsDialogs.PFSFlowsheetDialogs.40.0",
        ]:
            try:
                dialogs = win32.Dispatch(prog_id)
                break
            except Exception:
                continue
        if not dialogs:
            raise RuntimeError("PFSFlowsheetDialogs COM object not available.")
        before = set(_list_blocks(aspen))
        dialogs.UnplacedBlocksDialogAddBlock(model)
        time.sleep(2)
        after = set(_list_blocks(aspen))
        created = list(after - before)
        if created:
            created_name = created[0]
            if created_name != name:
                try:
                    blocks_node.RenameChild(created_name, name)
                except Exception:
                    pass
        time.sleep(1)
    else:
        raise RuntimeError(f"Unknown strategy: {strategy.name}")

    if not _verify_block(aspen, name):
        raise RuntimeError(f"Block '{name}' failed verification after creation.")

    if logger:
        logger.log(f"Created block '{name}' using strategy '{strategy.name}'.")


def _list_blocks(aspen) -> list:
    blocks_node = _ensure_blocks_node(aspen)
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
