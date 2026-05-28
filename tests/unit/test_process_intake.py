from __future__ import annotations

import json
from pathlib import Path

import pytest

from aspen_automation import build_process_intake_artifacts


def test_process_intake_artifacts_are_deterministic_codex_handoff(tmp_path: Path) -> None:
    artifacts = build_process_intake_artifacts(
        "ammonia_loop",
        tmp_path / "process_library",
        user_process_brief="Synthesize ammonia from nitrogen and hydrogen.",
        source_pdfs=[r"C:\refs\ammonia.pdf", "relative/design.pdf"],
        source_urls=["https://example.com/process"],
        web_search_queries=["industrial ammonia synthesis loop operating pressure"],
        reference_notes=["Use a compressor and synthesis reactor.", "Recycle unreacted gas."],
    )

    assert artifacts.process_name == "ammonia_loop"
    assert artifacts.process_dir == tmp_path / "process_library" / "ammonia_loop"
    assert artifacts.source_manifest_path.is_file()
    assert artifacts.research_brief_path.is_file()
    assert artifacts.codex_prompt_path.is_file()

    manifest = json.loads(artifacts.source_manifest_path.read_text(encoding="utf-8"))
    assert manifest["process_name"] == "ammonia_loop"
    assert manifest["source_pdfs"] == ["C:/refs/ammonia.pdf", "relative/design.pdf"]
    assert manifest["source_urls"] == ["https://example.com/process"]
    assert manifest["web_search_queries"] == ["industrial ammonia synthesis loop operating pressure"]
    assert manifest["llm_execution"] == "notebook does not call an LLM; pass these artifacts to Codex"

    brief = artifacts.research_brief_path.read_text(encoding="utf-8")
    assert "Synthesize ammonia from nitrogen and hydrogen." in brief
    assert "Use this evidence to create or revise `process_library/ammonia_loop/process.yaml`." in brief

    prompt = artifacts.codex_prompt_path.read_text(encoding="utf-8")
    assert "Create or revise `process_library/ammonia_loop/process.yaml`" in prompt
    assert "- `components`" in prompt
    assert "- `flowsheet`" in prompt
    assert "Choose equipment from the requested process, not from the methanol example by default." in prompt


def test_process_intake_rejects_unsafe_process_names(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="process_name"):
        build_process_intake_artifacts("../bad", tmp_path)
