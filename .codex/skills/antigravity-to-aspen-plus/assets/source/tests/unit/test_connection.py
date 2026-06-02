from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.skipif(
    os.environ.get("ASPEN_PLUS_INTEGRATION") != "1",
    reason="Set ASPEN_PLUS_INTEGRATION=1 to run the live Aspen Plus connection smoke test",
)


def test_aspen_plus_connection_methods() -> None:
    try:
        import win32com.client as win32
    except Exception as exc:  # pragma: no cover - environment-specific
        pytest.skip(f"pywin32 is not available: {exc}")

    errors: list[str] = []
    for method_name in ("GetActiveObject", "Dispatch", "DispatchEx"):
        method = getattr(win32, method_name)
        try:
            aspen = method("Apwn.Document")
            assert aspen.Name
            getattr(aspen, "Visible")
            return
        except Exception as exc:
            errors.append(f"{method_name}: {exc}")

    pytest.fail(
        "All Aspen Plus connection methods failed. "
        "Confirm Aspen Plus is installed, running, and has a simulation file open. "
        + " | ".join(errors)
    )
