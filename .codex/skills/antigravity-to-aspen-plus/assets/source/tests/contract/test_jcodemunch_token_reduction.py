from __future__ import annotations

import asyncio
import json
import os
import shutil
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest

tiktoken = pytest.importorskip("tiktoken")
mcp = pytest.importorskip("mcp")
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


REPO_ROOT = Path(__file__).resolve().parents[2]
ASPN_AUTOMATION_ROOT = REPO_ROOT / "aspen_automation"
START_SCRIPT = REPO_ROOT / "tools" / "start_jcodemunch_mcp.ps1"
TOKENIZER_NAME = "cl100k_base"
MIN_REDUCTION_PCT = 30.0
TASK_PROMPT = (
    "Find the helper that builds Aspen stream result rows with mole and mass "
    "fractions, then inspect the helper it uses to read Aspen node values."
)
BASELINE_FILES = (
    ASPN_AUTOMATION_ROOT / "extractor.py",
    ASPN_AUTOMATION_ROOT / "reporter.py",
    ASPN_AUTOMATION_ROOT / "process_results_analysis.py",
)
SEARCH_QUERIES = (
    "Aspen stream row output fractions",
    "node value Aspen stream output helper",
)
TARGET_SYMBOLS = (
    ("_extract_stream_row", "extractor.py"),
    ("_get_node_value", "extractor.py"),
)


def _tokenizer():
    return tiktoken.get_encoding(TOKENIZER_NAME)


def _count_tokens(text: str) -> int:
    return len(_tokenizer().encode(text))


def _baseline_bundle() -> str:
    sections = [f"TASK\n{TASK_PROMPT}"]
    for file_path in BASELINE_FILES:
        sections.append(f"FILE: {file_path.relative_to(REPO_ROOT)}\n{file_path.read_text(encoding='utf-8')}")
    return "\n\n".join(sections)


def _make_repo_local_tempdir() -> Path:
    base_dir = REPO_ROOT / "pytest_tmp"
    base_dir.mkdir(exist_ok=True)
    path = base_dir / f"jcodemunch_benchmark_{uuid4().hex}"
    path.mkdir()
    return path


def _call_result_to_json(result) -> dict:
    text = "".join(getattr(item, "text", "") for item in result.content)
    return json.loads(text)


def _find_symbol_id(search_payload: dict, *, name: str, file_name: str) -> str:
    for item in search_payload.get("results", []):
        if item.get("name") == name and item.get("file") == file_name:
            return item["id"]
    raise AssertionError(f"Did not find symbol {name!r} in {file_name!r}: {search_payload}")


async def _mcp_bundle(storage_path: Path) -> str:
    env = dict(os.environ)
    env["CODE_INDEX_PATH"] = str(storage_path.resolve())

    server_params = StdioServerParameters(
        command="pwsh",
        args=["-File", str(START_SCRIPT)],
        env=env,
        cwd=str(REPO_ROOT),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            index_payload = _call_result_to_json(
                await session.call_tool(
                    "index_folder",
                    {"path": str(ASPN_AUTOMATION_ROOT), "use_ai_summaries": False},
                    read_timeout_seconds=timedelta(seconds=120),
                )
            )
            repo_id = index_payload["repo"]

            query_payloads: dict[str, dict] = {}
            for query in SEARCH_QUERIES:
                query_payloads[query] = _call_result_to_json(
                    await session.call_tool(
                        "search_symbols",
                        {"repo": repo_id, "query": query, "max_results": 5},
                        read_timeout_seconds=timedelta(seconds=30),
                    )
                )

            symbol_sources = []
            for symbol_name, file_name in TARGET_SYMBOLS:
                matching_payload = next(
                    payload
                    for payload in query_payloads.values()
                    if any(
                        item.get("name") == symbol_name and item.get("file") == file_name
                        for item in payload.get("results", [])
                    )
                )
                symbol_id = _find_symbol_id(matching_payload, name=symbol_name, file_name=file_name)
                symbol_sources.append(
                    _call_result_to_json(
                        await session.call_tool(
                            "get_symbol_source",
                            {"repo": repo_id, "symbol_id": symbol_id},
                            read_timeout_seconds=timedelta(seconds=30),
                        )
                    )
                )

    bundle = {
        "task": TASK_PROMPT,
        "repo": "aspen_automation",
        "queries": query_payloads,
        "symbols": symbol_sources,
    }
    return json.dumps(bundle, indent=2, sort_keys=True)


def test_jcodemunch_reduces_tokens_for_real_lookup() -> None:
    assert START_SCRIPT.exists(), f"Missing MCP launcher: {START_SCRIPT}"

    baseline_bundle = _baseline_bundle()
    temp_dir = _make_repo_local_tempdir()
    try:
        mcp_bundle = asyncio.run(_mcp_bundle(temp_dir / "jcodemunch-index"))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    baseline_tokens = _count_tokens(baseline_bundle)
    skill_tokens = _count_tokens(mcp_bundle)
    reduction_tokens = baseline_tokens - skill_tokens
    reduction_pct = (reduction_tokens / baseline_tokens) * 100 if baseline_tokens else 0.0

    metrics = {
        "baseline_tokens": baseline_tokens,
        "skill_tokens": skill_tokens,
        "reduction_tokens": reduction_tokens,
        "reduction_pct": round(reduction_pct, 2),
        "tokenizer": TOKENIZER_NAME,
    }
    print(json.dumps(metrics, indent=2, sort_keys=True))

    assert skill_tokens < baseline_tokens, metrics
    assert reduction_pct >= MIN_REDUCTION_PCT, metrics
