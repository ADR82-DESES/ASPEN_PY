# jCodeMunch MCP for Codex

This repo vendors `jgravelle/jcodemunch-mcp` under `third_party/jcodemunch-mcp` and includes a project-scoped Codex MCP config in `.codex/config.toml`.

## What is already wired

- Codex project config: `.codex/config.toml`
- jCodeMunch project config: `.jcodemunch.jsonc`
- Server launcher: `tools/start_jcodemunch_mcp.ps1`
- Default local index path: `.jcodemunch-cache/`

The launcher starts the vendored source tree with the Pixi interpreter at `.pixi/envs/default/python.exe`, so the MCP server stays local to this workspace.

## One-time setup

1. Install the workspace environment:

```powershell
pixi install
```

2. Verify the vendored source tree exists:

```powershell
Get-ChildItem third_party/jcodemunch-mcp
```

3. Open Codex from this repo root. Codex supports project-scoped MCP configuration in `.codex/config.toml`, so no global config edit is required for this workspace.

## Optional Codex CLI registration

If you prefer an explicit CLI command instead of relying on the committed project config, Codex documents MCP registration through `codex mcp add`:

```powershell
codex mcp add jcodemunch -- pwsh -File tools/start_jcodemunch_mcp.ps1
codex mcp list
```

Official Codex MCP docs:

- https://developers.openai.com/codex/mcp
- https://developers.openai.com/learn/docs-mcp

## Recommended Codex instruction

Add this to your repo `AGENTS.md` or equivalent policy file if you want Codex to prefer jCodeMunch consistently:

```markdown
Always use the jcodemunch MCP server for code lookup in this repository. Prefer resolve_repo, index_folder, search_symbols, get_file_outline, and get_symbol_source over broad file reads when you are locating code.
```

## Verification

Use these checks in a fresh Codex session opened from this repo:

1. Run `/mcp` in the Codex TUI and confirm `jcodemunch` is enabled.
2. Ask Codex to index `aspen_automation`.
3. Ask a lookup question such as: `Find the helper that builds Aspen stream result rows and the node-value helper it uses.`

The benchmark below validates the same retrieval pattern with a live stdio MCP session:

```powershell
.\.pixi\envs\default\python.exe -m pytest tests/contract/test_jcodemunch_token_reduction.py -v -s
```
