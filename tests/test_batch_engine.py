from __future__ import annotations

import os
from pathlib import Path

from aspen_automation.batch_engine import (
    collect_batch_artifacts,
    make_unique_run_id,
    parse_aspen_history,
    run_aspen_batch,
    sanitize_run_id,
)


ROOT = Path(__file__).resolve().parents[1]


def test_sanitize_run_id_is_lowercase_alphanumeric_and_eight_chars() -> None:
    run_id = sanitize_run_id("Methanol Plant Generated")

    assert run_id.startswith("methan")
    assert len(run_id) <= 8
    assert run_id.isalnum()
    assert run_id == run_id.lower()


def test_make_unique_run_id_avoids_existing_artifacts(tmp_path: Path) -> None:
    tmp_path.joinpath("methanol.bkp").write_text("old", encoding="utf-8")

    assert make_unique_run_id("methanol", tmp_path) == "methan01"


def test_parse_aspen_history_extracts_translation_errors() -> None:
    history = ROOT / "Methanol Plant" / "MethanolPlant.his"
    source = ROOT / "Methanol Plant" / "MethanolPlant.inp"

    diagnostics = parse_aspen_history(history, source_inp_path=source)

    assert diagnostics["status"] == "failed"
    assert diagnostics["input_translation_failed"] is True
    assert diagnostics["summary_counts"]["severe_errors"]["system"] == 27
    assert diagnostics["messages"][0]["severity"] == "severe"
    assert diagnostics["messages"][0]["input_line"] == 27
    assert "FLOWSHEETING" in diagnostics["messages"][0]["message"]


def test_collect_batch_artifacts_reports_missing_files(tmp_path: Path) -> None:
    tmp_path.joinpath("case.bkp").write_text("backup", encoding="utf-8")

    artifacts = collect_batch_artifacts(tmp_path, "case")

    assert artifacts[".bkp"]["exists"] is True
    assert artifacts[".sum"]["exists"] is False


def test_run_aspen_batch_uses_isolated_directory_and_collects_outputs(tmp_path: Path) -> None:
    inp_path = tmp_path / "source.inp"
    inp_path.write_text("TITLE 'TEST'\n", encoding="utf-8")
    batch_dir = tmp_path / "batch"
    fake_engine = tmp_path / "fake_aspen.cmd"
    fake_engine.write_text(
        "\r\n".join(
            [
                "@echo off",
                "set RUNID=%1",
                "echo fake stdout",
                "echo history for %RUNID%>%RUNID%.his",
                "echo backup>%RUNID%.bkp",
                "echo MMSUMMARY40.0>%RUNID%.sum",
                "exit /b 0",
            ]
        ),
        encoding="utf-8",
    )

    result = run_aspen_batch(
        inp_path,
        batch_dir,
        run_id="Methanol Plant",
        timeout_seconds=30,
        engine_path=str(fake_engine),
    )

    assert result.succeeded is True
    assert result.run_id.startswith("methan")
    assert len(result.run_id) <= 8
    assert result.command == [str(fake_engine), result.run_id, result.run_id, "/mmbackup", "/log"]
    assert result.artifacts[".bkp"]["exists"] is True
    assert Path(result.input_path).parent == batch_dir.resolve()
    assert Path(result.stdout_path).read_text(encoding="utf-8").strip() == "fake stdout"


def test_run_aspen_batch_reports_missing_engine(tmp_path: Path) -> None:
    inp_path = tmp_path / "source.inp"
    inp_path.write_text("TITLE 'TEST'\n", encoding="utf-8")

    old_engine = os.environ.pop("ASPEN_ENGINE_PATH", None)
    try:
        result = run_aspen_batch(
            inp_path,
            tmp_path / "batch",
            run_id="case",
            engine_path=str(tmp_path / "missing_aspen.exe"),
        )
    finally:
        if old_engine is not None:
            os.environ["ASPEN_ENGINE_PATH"] = old_engine

    assert result.succeeded is False
    assert result.error is not None
    assert "return code" in result.error or "not found" in result.error
