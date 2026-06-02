"""
Integration test for loading generated INP files via Aspen Plus COM.

Requirements:
- Aspen Plus installed and registered for COM automation.
- 32/64-bit Python must match Aspen Plus COM registration.
- Run on an interactive desktop session (COM UI may initialize).
- Set ASPEN_PLUS_INTEGRATION=1 to enable the test.
"""
import os
import shutil
import uuid
from pathlib import Path

import pytest

from aspen_automation import load_spec, generate_inp
from aspen_automation.session import (
    check_aspen_v14_connection,
    _import_file_with_verification,
    _verify_flowsheet,
)

try:
    import win32com.client as win32
    import pythoncom
except Exception:  # pragma: no cover - environment-specific
    win32 = None
    pythoncom = None


def test_inp_com_load():
    if win32 is None:
        pytest.skip("pywin32 not installed")

    if os.environ.get("ASPEN_PLUS_INTEGRATION") != "1":
        pytest.skip("Set ASPEN_PLUS_INTEGRATION=1 to run Aspen Plus COM test")

    preflight = check_aspen_v14_connection(visible=False)
    full_name = (
        preflight.get("identity_probe", {})
        .get("document", {})
        .get("FullName", "")
    )
    assert preflight["v14_verified"] is True or (
        preflight["preflight_status"] == "connected_version_unreported"
        and "Aspen Plus V14.0" in str(full_name)
    )

    spec_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures", "valid_plant.yaml"))
    spec = load_spec(spec_path)

    inp_content = generate_inp(spec)

    temp_root = Path(__file__).resolve().parents[2] / "test_results"
    temp_root.mkdir(exist_ok=True)
    tmpdir_path = temp_root / f"inp_com_load_{uuid.uuid4().hex}"
    tmpdir_path.mkdir(exist_ok=False)
    try:
        tmpdir = str(tmpdir_path)
        inp_path = os.path.join(tmpdir, "generated.inp")
        with open(inp_path, "w", encoding="utf-8") as f:
            f.write(inp_content)

        dispatch_ex = getattr(win32, "DispatchEx", None)
        aspen = dispatch_ex("Apwn.Document") if callable(dispatch_ex) else win32.Dispatch("Apwn.Document")
        aspen.SuppressDialogs = 1
        aspen.Visible = False

        loaded = False
        diagnostics = {}
        try:
            aspen.InitFromFile2(inp_path)
            diagnostics = _verify_flowsheet(aspen)
            loaded = True
        except Exception:
            loaded = False

        if not loaded:
            aspen.InitNew()
            diagnostics = _import_file_with_verification(
                aspen,
                inp_path,
                build_mode="integration",
            )
            loaded = True

        assert loaded, "Failed to load INP using InitFromFile2 or Import"
        assert diagnostics["build_valid"]

        for block in spec.blocks:
            node = aspen.Tree.FindNode(rf"\Data\Blocks\{block.name}")
            assert node is not None, f"Block '{block.name}' not found in Aspen tree"

        for stream in spec.streams:
            node = aspen.Tree.FindNode(rf"\Data\Streams\{stream.name}")
            assert node is not None, f"Stream '{stream.name}' not found in Aspen tree"

        try:
            aspen.Close(False)
        except Exception:
            pass
    finally:
        shutil.rmtree(tmpdir_path, ignore_errors=True)
