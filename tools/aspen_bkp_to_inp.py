"""Translate an Aspen Plus archive (.bkp/.apw/.apwz) into an input-language .inp.

Aspen's GUI ``.bkp`` files store the simulation in the GUI keyword dialect
(``REAC-DATA … REAC-CLASS=LHHW``, ``DFORCE-EQ-1``, ``ADSORP-EXP`` …). The batch
engine, however, consumes the *input language* (``REACTIONS … LHHW`` with its own
keyword spellings). The only authoritative way to learn those input-language
keywords is to let Aspen itself emit them, which is exactly what File > Export >
Input File does in the GUI. This script performs that export headlessly over COM,
reusing the dispatch pattern proven in ``aspen_automation/session.py``.

Usage:
    pixi run python tools/aspen_bkp_to_inp.py <archive.bkp> <out.inp>

It is deliberately defensive about the export method name: the Aspen Plus
``Apwn.Document`` COM object exposes the export under a couple of signatures
across versions, so we try the known candidates and report which one worked.
"""
from __future__ import annotations

import os
import sys

ASPEN_DOCUMENT_PROG_ID = "Apwn.Document"


def _dispatch():
    import win32com.client as win32  # noqa: WPS433 (import guarded by caller env)

    dispatch_ex = getattr(win32, "DispatchEx", None)
    if callable(dispatch_ex):
        try:
            return dispatch_ex(ASPEN_DOCUMENT_PROG_ID)
        except Exception:  # noqa: BLE001 - fall back to plain Dispatch
            pass
    return win32.Dispatch(ASPEN_DOCUMENT_PROG_ID)


def _quiet(aspen) -> None:
    for attr, value in (("Visible", 0), ("SuppressDialogs", 1)):
        try:
            setattr(aspen, attr, value)
        except Exception:  # noqa: BLE001 - best-effort, some props need init first
            pass


def _try_export(aspen, out_path: str) -> str:
    """Attempt each known export signature; return the description that worked.

    The Aspen Plus ``Apwn.Document.Export`` signature is ``Export(FileType, FileName)``
    where ``FileType`` is an integer format code. Empirically (V14): 1=backup(.bkp),
    3=summary(.sum), 4=input language(.inp), 6=control(.cpm). Code 4 is the
    input-language deck the batch engine consumes, so it is tried first.
    """
    candidates = [
        ("Export(4=input, out)", lambda: aspen.Export(4, out_path)),
        ("Export(0, out)", lambda: aspen.Export(0, out_path)),
        ("Export(out)", lambda: aspen.Export(out_path)),
    ]
    errors = []
    for desc, call in candidates:
        try:
            call()
        except Exception as exc:  # noqa: BLE001 - probing signatures
            errors.append(f"  {desc}: {type(exc).__name__}: {exc}")
            continue
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return desc
        errors.append(f"  {desc}: call returned but no file was written")
    raise RuntimeError("No export signature succeeded:\n" + "\n".join(errors))


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    archive_path = os.path.abspath(argv[1])
    out_path = os.path.abspath(argv[2])
    if not os.path.exists(archive_path):
        print(f"ERROR: archive not found: {archive_path}")
        return 2
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    if os.path.exists(out_path):
        os.remove(out_path)

    print(f"Loading archive: {archive_path}")
    aspen = _dispatch()
    try:
        aspen.InitFromArchive2(archive_path)
        _quiet(aspen)
        print(f"Exporting input file: {out_path}")
        used = _try_export(aspen, out_path)
        size = os.path.getsize(out_path)
        print(f"OK via {used} -> {out_path} ({size} bytes)")
        return 0
    finally:
        for closer in ("Close", "Quit"):
            try:
                getattr(aspen, closer)(False) if closer == "Close" else getattr(aspen, closer)()
            except Exception:  # noqa: BLE001 - best-effort teardown
                pass


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
