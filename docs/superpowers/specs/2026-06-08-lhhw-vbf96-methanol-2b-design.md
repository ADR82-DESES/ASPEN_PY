# VBF96 LHHW Methanol Parameterization (2b) — Design

**Date:** 2026-06-08
**Status:** Approved (design)
**Branch:** `feature/lhhw-kinetics` (stacks on 2a, in the worktree)
**Part of:** Process-fidelity upgrade item #2. 2a built the generic LHHW capability; **2b** uses
it to give the methanol synthesis reactor real Vanden Bussche–Froment kinetics.

## Problem

`process_library/methanol/process.yaml` drives `B-SYN` (RPLUG) with three `POWERLAW`
placeholder reactions whose activation energies are 0 (`kinetic_models: VBF96_SCREENING`,
explicitly "uncalibrated screening defaults"). The result is not design-grade.

## Goal

Replace the placeholders with the canonical **2-reaction CO₂-based VBF model** using the exact,
Aspen-validated constants from Aspen's own `methanol synthesis lab reactor` example (the same
deck 2a's reference INP was extracted from), expressed through the 2a LHHW schema.

## Decisions (user-approved)

- **Constants:** the Aspen reference-deck values (not a from-memory literature transcription).
- **Property method:** unchanged. Physical accuracy of the loop needs an EOS (item #1); 2b does
  not touch the property method.
- **Catalyst basis:** keep the reference's `RBASIS=CAT-WT`, so `B-SYN` must carry catalyst
  loading and the generator must emit it (see Generator additions).

## Reactions (mapping the reference deck's `MEOH` → this deck's `CH3OH`)

Both reactions: `reaction_type: LHHW`, `phase: V`, `conc_basis: PARTIALPRES` (CBASIS),
`cat_basis: CAT-WT` (RBASIS), `reversible: true`, `rev_method: USER-SPEC`, `pres_unit: BAR`.

### Reaction 1 — RWGS: CO₂ + H₂ → CO + H₂O  (`name: RWGS`)

- stoichiometry: CO2 −1, H2 −1, CO 1, H2O 1
- kinetic_factor: `pre_exp 0.00165`, `act_energy 22.6342`, `act_energy_unit kcal/mol`,
  `t_ref 228.42`, `t_ref_unit K`
- driving_force.term1: exponents `{CO2: 1}`, coeff `[0.0, 0.0]`  (K₁ = 1)
- driving_force.term2: exponents `{H2: -1, CO: 1, H2O: 1}`, coeff `[-4.671945154, 4773.258898]`
- adsorption: `power 1.0`; exponents `{H2O: [0,1,0,1], H2: [0,-1,0.5,0]}`;
  terms `[[0.0], [8.147108741, 0.0], [-0.6951, 2068.3], [-23.438, 14928.19686]]`

### Reaction 2 — MeOH synthesis: CO₂ + 3H₂ → CH₃OH + H₂O  (`name: MEOH-SYN`)

- stoichiometry: CO2 −1, H2 −3, CH3OH 1, H2O 1
- kinetic_factor: `pre_exp 7.07034`, `act_energy -8.76469`, `act_energy_unit kcal/mol`,
  `t_ref 228.42`, `t_ref_unit K`
- driving_force.term1: exponents `{CO2: 1, H2: 1}`, coeff `[0.0, 0.0]`  (K₁ = 1)
- driving_force.term2: exponents `{H2: -2, CH3OH: 1, H2O: 1}`, coeff `[24.3889813, -7059.72589]`
- adsorption: `power 3.0`; exponents `{H2O: [0,1,0,1], H2: [0,-1,0.5,0]}`;
  terms `[[0.0], [8.147108741, 0.0], [-0.69515, 2068.3], [-23.43827453, 14928.19686]]`

`reaction_sets`: `RXN-SET1` → `block_type: GENERAL`, `reaction_ids: [1, 2]`.

## Units — the one subtlety (and why it is handled)

The reference deck is `IN-UNITS SI` (temperature K); this deck is `IN-UNITS MET` (temperature
°C). Audit of unit sensitivity:

- **ACT-ENERGY** — carries an explicit `<kcal/mol>` token → unit-independent. Transcribe as-is.
- **Driving-force / adsorption A,B** (in `exp(A + B/T + …)`) — Aspen evaluates these with
  **absolute temperature (K)** regardless of `IN-UNITS` → transcribe as-is.
- **T-REF** — a RATE-CON reference temperature that *is* governed by `IN-UNITS`. A bare
  `T-REF=228.42` in a MET deck would mean 228.42 °C ≈ 502 K, not the intended 228.42 K.
  **Mitigation:** emit an explicit unit token — `T-REF=228.42 <K>` — so the reference
  temperature is unambiguous and matches the SI reference deck. This is the primary Gate-1
  check; if Aspen rejects a token on T-REF, the fallback is to convert (228.42 K = −44.73 °C).

## Architecture

### Generator additions (`aspen_automation/inp_generator.py`)

1. **RPLUG catalyst loading.** In `_generate_rplug_block`, when the block parameters contain
   `CAT-WT`, add `CAT-PRESENT=YES` and `CATWT=<value>` to the emitted RPLUG PARAM line. (The
   value lives in `B-SYN.parameters.CAT-WT = 250000.0`; only emission is missing.) No unit token
   (MET base mass = kg).
2. **LHHW T-REF unit token.** Add `t_ref_unit: Optional[str] = None` to `LhhwKineticFactor`
   (`schema.py`); `_generate_lhhw_reactions` emits `T-REF=<v> <unit>` when set, else `T-REF=<v>`.
   Mirrors the existing `act_energy_unit` handling.

### Data (`process_library/methanol/process.yaml`)

- `chemistry.MEOH-KINETIC.reactions`: replace the 3 POWERLAW reactions with the 2 LHHW reactions
  above.
- `reaction_sets.RXN-SET1`: `POWERLAW` → `GENERAL`, `reaction_ids: [1, 2]`.
- `kinetic_models`: rewrite the `VBF96_SCREENING` entry to describe the real LHHW model, cite the
  provenance (Aspen V14 `methanol synthesis lab reactor` example → `lhhw_reference.inp`), record
  the T-REF=K unit decision, and drop the "uncalibrated/Ea=0" language.
- `B-SYN` keeps `CAT-WT: 250000.0` (now actually emitted).

## Testing

- **Generator unit tests:** RPLUG with `CAT-WT` emits `CAT-PRESENT=YES CATWT=250000.0`; an LHHW
  reaction with `t_ref_unit="K"` emits `T-REF=228.42 <K>`.
- **Integration test:** `generate_inp(load_spec(methanol process.yaml))` produces a valid INP
  whose `REACTIONS RXN-SET1 GENERAL` block contains both reactions' `REAC-DATA … REAC-CLASS=LHHW`,
  the RWGS/MEOH-SYN `RATE-CON` lines with `T-REF=228.42 <K>`, `ADSORP-POW REACNO=1 EXPONENT=1.0 /
  REACNO=2 EXPONENT=3.0`, and that `B-SYN` emits `CAT-PRESENT=YES CATWT=250000.0`; `validate_spec`
  passes.

## Validation boundary

Claude delivers the generator additions + the wired `process.yaml` + headless tests that the
deck emits the designed LHHW/catalyst keywords and validates. **The user owns Gate-1:**
Aspen batch-translates the deck (clean `.his`), `B-SYN` converges, and methanol conversion is
credible. Physically-accurate loop behavior may still require item #1 (EOS) and item #3 (SN
adjustment); 2b delivers the kinetics, not the full design-grade loop.

## Out of scope

- Property-method / EOS change (item #1), H₂ recovery for SN≈2 (item #3), two-column
  distillation (item #4).
- Catalyst deactivation, intraparticle diffusion, or bed-voidage/pressure-drop tuning beyond
  emitting the catalyst weight.
