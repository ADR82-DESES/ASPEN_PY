from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


_PROCESS_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


@dataclass(frozen=True)
class ProcessIntakeArtifacts:
    process_name: str
    process_dir: Path
    assets_dir: Path
    source_manifest_path: Path
    research_brief_path: Path
    codex_prompt_path: Path


def build_process_intake_artifacts(
    process_name: str,
    process_library_root: str | Path = "process_library",
    *,
    user_process_brief: str = "",
    source_pdfs: Sequence[str | Path] = (),
    source_urls: Sequence[str] = (),
    web_search_queries: Sequence[str] = (),
    reference_notes: str | Sequence[str] = (),
) -> ProcessIntakeArtifacts:
    """Write deterministic evidence artifacts for Codex-authored process YAML.

    The helper records the user's sources and prompt context; it does not perform
    web searches, read PDFs, or call an LLM. That keeps the notebook workflow
    transparent while giving Codex a stable handoff format.
    """

    normalized_name = _validate_process_name(process_name)
    process_root = Path(process_library_root).expanduser().resolve()
    process_dir = process_root / normalized_name
    assets_dir = process_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    notes = _normalize_notes(reference_notes)
    pdf_entries = [_source_path(path) for path in source_pdfs]
    url_entries = [str(url).strip() for url in source_urls if str(url).strip()]
    query_entries = [str(query).strip() for query in web_search_queries if str(query).strip()]

    source_manifest_path = assets_dir / "source_manifest.json"
    research_brief_path = assets_dir / "process_research_brief.md"
    codex_prompt_path = assets_dir / "codex_process_yaml_prompt.md"

    manifest = {
        "process_name": normalized_name,
        "process_dir": _posix_path(process_dir),
        "intake_artifacts": {
            "source_manifest": _posix_path(source_manifest_path),
            "process_research_brief": _posix_path(research_brief_path),
            "codex_process_yaml_prompt": _posix_path(codex_prompt_path),
        },
        "user_process_brief": user_process_brief.strip(),
        "source_pdfs": pdf_entries,
        "source_urls": url_entries,
        "web_search_queries": query_entries,
        "reference_notes": notes,
        "llm_execution": "notebook does not call an LLM; pass these artifacts to Codex",
    }
    source_manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    research_brief_path.write_text(
        _build_research_brief(
            normalized_name,
            user_process_brief=user_process_brief,
            source_pdfs=pdf_entries,
            source_urls=url_entries,
            web_search_queries=query_entries,
            reference_notes=notes,
        ),
        encoding="utf-8",
    )
    codex_prompt_path.write_text(
        _build_codex_prompt(
            normalized_name,
            source_manifest_path=source_manifest_path,
            research_brief_path=research_brief_path,
        ),
        encoding="utf-8",
    )

    return ProcessIntakeArtifacts(
        process_name=normalized_name,
        process_dir=process_dir,
        assets_dir=assets_dir,
        source_manifest_path=source_manifest_path,
        research_brief_path=research_brief_path,
        codex_prompt_path=codex_prompt_path,
    )


def _validate_process_name(process_name: str) -> str:
    normalized = str(process_name).strip()
    if not normalized:
        raise ValueError("process_name is required")
    if not _PROCESS_NAME_RE.match(normalized):
        raise ValueError("process_name must contain only letters, digits, underscores, and hyphens")
    return normalized


def _normalize_notes(reference_notes: str | Sequence[str]) -> list[str]:
    if isinstance(reference_notes, str):
        notes = [line.strip() for line in reference_notes.splitlines()]
    else:
        notes = [str(note).strip() for note in reference_notes]
    return [note for note in notes if note]


def _build_research_brief(
    process_name: str,
    *,
    user_process_brief: str,
    source_pdfs: Sequence[str],
    source_urls: Sequence[str],
    web_search_queries: Sequence[str],
    reference_notes: Sequence[str],
) -> str:
    lines = [
        f"# Process Research Brief: {process_name}",
        "",
        "## User Process Brief",
        user_process_brief.strip() or "_No brief provided yet._",
        "",
        "## Source PDFs",
        *_bullet_lines(source_pdfs),
        "",
        "## Source URLs",
        *_bullet_lines(source_urls),
        "",
        "## Web Search Queries To Run Outside The Notebook",
        *_bullet_lines(web_search_queries),
        "",
        "## Reference Notes",
        *_bullet_lines(reference_notes),
        "",
        "## Codex Task",
        f"Use this evidence to create or revise `process_library/{process_name}/process.yaml`.",
        "Keep methanol-specific assumptions out unless the requested process is methanol.",
        "",
    ]
    return "\n".join(lines)


def _build_codex_prompt(process_name: str, *, source_manifest_path: Path, research_brief_path: Path) -> str:
    return "\n".join(
        [
            f"# Codex Process YAML Prompt: {process_name}",
            "",
            f"Create or revise `process_library/{process_name}/process.yaml` using the existing process-library schema.",
            "",
            "Use these artifacts as source context:",
            f"- `{_posix_path(source_manifest_path)}`",
            f"- `{_posix_path(research_brief_path)}`",
            "",
            "Required YAML sections:",
            "- `metadata`",
            "- `components`",
            "- `properties`",
            "- `flowsheet`",
            "- `streams`",
            "- `blocks`",
            "",
            "Optional sections when supported by the process:",
            "- `chemistry`",
            "- `reaction_sets`",
            "- `kinetic_models`",
            "- `process_defaults`",
            "- `targets`",
            "",
            "Implementation rules:",
            "- Choose equipment from the requested process, not from the methanol example by default.",
            "- Define every stream and block referenced by `flowsheet`.",
            "- Use Aspen batch-translatable block types and parameter names supported by the local generator.",
            "- Set `process_defaults.product_stream` when production KPIs should use a specific stream.",
            "- Label screening assumptions clearly when literature or vendor data is incomplete.",
            "",
        ]
    )


def _bullet_lines(items: Sequence[str]) -> list[str]:
    if not items:
        return ["- _None provided._"]
    return [f"- {item}" for item in items]


def _posix_path(path: Path) -> str:
    return path.as_posix()


def _source_path(path: str | Path) -> str:
    return str(path).replace("\\", "/")


__all__ = ["ProcessIntakeArtifacts", "build_process_intake_artifacts"]
