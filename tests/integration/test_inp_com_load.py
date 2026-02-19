"""
Integration test for loading generated INP files via Aspen Plus COM.

Requirements:
- Aspen Plus installed and registered for COM automation.
- 32/64-bit Python must match Aspen Plus COM registration.
- Run on an interactive desktop session (COM UI may initialize).
- Set ASPEN_PLUS_INTEGRATION=1 to enable the test.
"""
import os
import tempfile

import pytest

from aspen_automation import load_spec, generate_inp

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

    spec_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures", "valid_plant.yaml"))
    spec = load_spec(spec_path)

    inp_content = generate_inp(spec)

    with tempfile.TemporaryDirectory() as tmpdir:
        inp_path = os.path.join(tmpdir, "generated.inp")
        with open(inp_path, "w", encoding="utf-8") as f:
            f.write(inp_content)

        aspen = win32.Dispatch("Apwn.Document")
        aspen.SuppressDialogs = 1
        aspen.Visible = False

        loaded = False
        try:
            aspen.InitFromFile2(inp_path)
            loaded = True
        except Exception:
            loaded = False

        if not loaded:
            aspen.InitNew()
            path_variant = win32.VARIANT(pythoncom.VT_BSTR, inp_path)
            try:
                aspen.Import(path_variant)
                loaded = True
            except Exception:
                data_node = aspen.Tree.FindNode(r"\Data")
                data_node.Import(path_variant)
                loaded = True

        assert loaded, "Failed to load INP using InitFromFile2 or Import"

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
