---
name: antigravity-to-aspen-plus
description: Use when automating Aspen Plus process simulations from Python/COM in this repo — building or tuning the process_library decks (methanol ATR), hitting production/nameplate targets (e.g. 10k TPD), fixing RADFRAC purity/yield or bottoms_rate problems, COM zero-NRTL / binary-parameter warnings, vent/recycle recovery, or running run_process_batch_first acceptance gates.
---

# Antigravity to Aspen Plus (Claude entry point)

Aspen Plus process automation and deck tuning for this repo. The **canonical,
task-specific** skill and its deep-dive notes live under `.codex/` (shared with the Codex
agent). This file is the Claude Code entry point so the same knowledge is discoverable
here — it points at the source of truth rather than copying it.

## Read first (canonical)

- **Workflow, file selection, implementation patterns:**
  `.codex/skills/antigravity-to-aspen-plus/SKILL.md` — the authoritative skill (replication
  contract, batch-first gates, INP/equipment rules, notebook contract, test contract,
  methanol lessons).
- **General Aspen COM behavior (background only):** `.agent/rules/aspen-plus.md`.

## Deep-dive references

In `.codex/skills/antigravity-to-aspen-plus/references/` — read the relevant one before
working in that area:

- `self-similar-plant-scaling.md` — retarget a converged deck to a new nameplate by scaling
  the **extensive** inputs (fresh feeds, reactor `CAT-WT`/`LENGTH`) by one factor `k` while
  freezing the **intensive** specs (reflux, T/P, `DIAM`); why W/F, per-pass conversion, and
  SN stay constant; the kinetics-validity caveat.
- `radfrac-bottoms-rate.md` — a `RADFRAC` `bottoms_rate` is an **absolute** spec that must
  track the column-feed water+heavies load (re-track at every scale); the two failure
  directions; the methanol-slip vs purity cushion trade.
- `vent-recovery-tuning.md` — close acceptance on a rate-limited reactor by recovering
  vented product with a dedicated `FLASH2` (temperature sweet-spot, verified dead ends).
- `com-under-appsanywhere.md` — why the COM-launched engine emits the zero-NRTL
  (zero-binary-parameter) warning under virtualization, and when it is cosmetic vs. real.
- `binary-parameter-calibration.md`, `nrtl-bpval-syntax.md`, `aspen-databank-sql.md` —
  recovering real binary-interaction coefficients, the directional two-line `BPVAL` rule,
  and where Aspen stores databank parameters.

## Maintenance

`.codex/...` is the single source of truth — add/edit references **there**, not here. This
pointer only needs updating when a new reference topic is added or the canonical paths
move. (See the `codex-bundle-sync` memory for how the `.codex` bundle drifts from active
source.)
