from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.skipif(
    os.environ.get("ASPEN_PLUS_INTEGRATION") != "1",
    reason="Set ASPEN_PLUS_INTEGRATION=1 to run the live Aspen Plus COM smoke test",
)


def test_aspen_dispatch_initnew_smoke() -> None:
    try:
        import win32com.client as win32
    except Exception as exc:  # pragma: no cover - environment-specific
        pytest.skip(f"pywin32 is not available: {exc}")

    aspen = None
    try:
        aspen = win32.Dispatch("Apwn.Document")
        aspen.InitNew()
        assert aspen.Name
    finally:
        if aspen is not None:
            try:
                aspen.Quit()
            except Exception:
                pass
