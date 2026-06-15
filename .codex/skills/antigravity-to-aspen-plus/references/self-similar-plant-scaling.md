# Self-Similar Plant Scaling to a Production Target

A reusable way to retarget an **already-converged** flowsheet to a new nameplate
(e.g. 10k TPD) in 1–4 runs, without re-tuning topology, kinetics, or product specs.

## When this applies

- You have a converged deck producing `P0` and need `P_target` — same flowsheet, same
  chemistry, same product quality.
- You want production to move ~linearly and predictably, not to re-explore the design.

## Core idea: scale the extensive, freeze the intensive

Multiply every **extensive** (size/throughput) input by one factor `k = P_target / P0`.
Leave every **intensive** (per-unit, T/P, ratio) spec untouched.

| Scale by `k` (extensive)                          | Freeze (intensive)                            |
| ------------------------------------------------- | --------------------------------------------- |
| Fresh feed mass flows (each one, by the same `k`) | All T and P specs                             |
| Reactor catalyst inventory `CAT-WT`               | Reflux ratio, split fractions (PURGE/RECYCLE) |
| Reactor `LENGTH` (at **fixed** `DIAM`)            | Reactor `DIAM`, `BED-VOIDAGE`                 |

Scale **only the true fresh feeds** — never the recycle/intermediate streams; those
re-solve from the converged loop.

### Why it holds

Scaling `CAT-WT` and `LENGTH` **together** at fixed `DIAM` keeps catalyst **bed density**,
**W/F** (space velocity), **per-pass conversion**, and the loop **stoichiometric number
(SN)** constant. With those invariant, production scales ~linearly with `k`.

### Scale the reactor by its rate basis

- `RBASIS=CAT-WT` (LHHW / catalyst-weight kinetics): scale `CAT-WT`, and scale `LENGTH`
  with it to hold bed density.
- Volume / `MOLARITY` basis: scale reactor **volume** (`LENGTH` at fixed `DIAM`); `CAT-WT`
  is inert there.

## Procedure

1. `k0 = P_target / P0` from the last converged run.
2. Apply `k0` to the fresh feeds + reactor extensive params.
3. **Re-track absolute downstream rates** that are not topology-driven — above all the
   `RADFRAC` `bottoms_rate` — see `references/radfrac-bottoms-rate.md`. A scaled deck with
   a stale `bottoms_rate` reproduces the bottoms defect at the new scale.
4. Run; read `production_tpd`. Correct `k ← k · (P_target / production_tpd)`; repeat.
   Expect 1–4 runs.

## Validity caveat (re-scan for your process)

The linear argument assumes the deck's **actual** rate law. A `k` derived under one
kinetics model is **not** transferable to a deck with different kinetics (e.g. an LHHW `k`
applied to a POWERLAW / equilibrium deck) — re-derive `k0` against the deck you are
actually running.

## Verified example (LHHW methanol, CAT-WT-active deck)

`k0 = 0.6683` (target 10000 / ~14960 TPD at full scale):

| param                                  | full scale               | × 0.6683                 |
| -------------------------------------- | ------------------------ | ------------------------ |
| `NG-FEED` / `STEAM` / `O2-FEED`        | 440000 / 297000 / 528000 | 294052 / 198485 / 352862 |
| `B-SYN` `CAT-WT`                       | 250000                   | 167075                   |
| `B-SYN` `LENGTH`                       | 21.3                     | 14.235                   |
| `DIAM`, `reflux_ratio`                 | 4.0, 2.0                 | **unchanged**            |
| `bottoms_rate` (absolute — re-tracked) | 82000                    | 12200                    |

One run landed **9973.9 TPD** (target 10000 ±2%), purity **99.88%**, vent CH3OH
**20133 kg/hr**, `acceptance.passed == true`.
