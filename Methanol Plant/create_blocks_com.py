import os
import sys
import time
from pathlib import Path

import win32com.client as win32

from com_block_factory import BlockCreationStrategy, create_block
from com_block_probe import run_probe


PROJECT_DIR = Path(__file__).resolve().parent
ROOT_DIR = PROJECT_DIR.parent
LOG_DIR = ROOT_DIR / "logs"
LOG_PATH = LOG_DIR / "create_blocks_log.txt"
INP_PATH = PROJECT_DIR / "MethanolPlant.inp"
OUTPUT_BKP = PROJECT_DIR / "MethanolPlant_blocks_only.bkp"


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


def connect_aspen(logger: Logger):
    try:
        aspen = win32.GetActiveObject("Apwn.Document")
        logger.log("Connected to running Aspen Plus instance.")
        return aspen, True
    except Exception:
        aspen = win32.Dispatch("Apwn.Document")
        logger.log("Created new Aspen Plus instance via Dispatch.")
        return aspen, False


def ensure_initialized(aspen, logger: Logger, was_active: bool) -> None:
    try:
        _ = aspen.Tree.FindNode(r"\Data")
        return
    except Exception:
        if was_active:
            logger.log("Active instance not initialized; calling InitNew().")
        else:
            logger.log("Initializing new Aspen Plus case via InitNew().")
        aspen.InitNew()
        time.sleep(2)


def parse_components_from_inp(inp_path: Path) -> list:
    if not inp_path.exists():
        return []
    components = []
    in_section = False
    with open(inp_path, "r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith(";"):
                continue
            upper = stripped.upper()
            if upper.startswith("COMPONENTS"):
                in_section = True
                continue
            if in_section and (upper.startswith("PROPERTIES") or upper.startswith("FLOWSHEET")):
                break
            if in_section:
                token = stripped.split()[0].strip("/")
                if token and token != "/":
                    components.append(token)
    # De-dup preserve order
    seen = set()
    ordered = []
    for comp in components:
        if comp not in seen:
            seen.add(comp)
            ordered.append(comp)
    return ordered


def ensure_components(aspen, components: list, logger: Logger) -> None:
    if not components:
        logger.log("No components parsed; using default list.")
        components = ["CH4", "H2O", "O2", "CO", "CO2", "H2", "CH3OH", "N2"]

    comp_node = aspen.Tree.FindNode(r"\Data\Components\Specifications\Input\CAG_IDS")
    if not comp_node:
        comp_node = aspen.Tree.FindNode(r"\Data\Components\Specifications")

    if not comp_node:
        raise RuntimeError("Components node not found.")

    for comp in components:
        try:
            comp_node.Elements.Add(comp)
            logger.log(f"Added component: {comp}")
        except Exception:
            logger.log(f"Component already exists or failed to add: {comp}")


def ensure_property_method(aspen, logger: Logger) -> None:
    node = aspen.Tree.FindNode(r"\Data\Properties\Global\Input\METHOD")
    if not node:
        raise RuntimeError("Property method node not found.")
    node.Value = "RK-SOAVE"
    logger.log("Set property method to RK-SOAVE.")


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


def main() -> int:
    logger = Logger(LOG_PATH)
    logger.log("=" * 70)
    logger.log("CREATE METHANOL BLOCKS VIA COM (BLOCKS ONLY)")
    logger.log("=" * 70)

    probe_result = run_probe()
    if not probe_result.success:
        logger.log("Probe failed; COM-only block creation not supported in Aspen 40.x.")
        logger.log("See logs/com_block_probe_log.txt for details.")
        logger.close()
        return 1

    strategy = BlockCreationStrategy(
        name=probe_result.strategy,
        type_field=probe_result.type_field,
    )
    logger.log(f"Using strategy from probe: {strategy}")

    aspen, was_active = connect_aspen(logger)
    aspen.SuppressDialogs = 1
    aspen.Visible = True

    ensure_initialized(aspen, logger, was_active)
    ensure_property_method(aspen, logger)
    components = parse_components_from_inp(INP_PATH)
    ensure_components(aspen, components, logger)

    created = 0
    for block_name, block_type in TARGET_BLOCKS:
        try:
            create_block(aspen, block_name, block_type, strategy, logger=logger)
            created += 1
        except Exception as err:
            logger.log(f"FAILED: {block_name} ({block_type}) -> {err}")
            logger.close()
            return 1

    existing = set(list_blocks(aspen))
    missing = [name for name, _ in TARGET_BLOCKS if name not in existing]

    logger.log(f"Created/verified {created} blocks.")
    if missing:
        logger.log(f"Missing blocks: {missing}")
    else:
        logger.log("All blocks present.")

    try:
        aspen.SaveAs(str(OUTPUT_BKP))
        logger.log(f"Saved: {OUTPUT_BKP}")
    except Exception as err:
        logger.log(f"Failed to save output BKP: {err}")
        logger.close()
        return 1

    logger.log("Done.")
    logger.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
