# LHHW Kinetics Capability (2a) — Design

**Date:** 2026-06-08
**Status:** Approved (design); **UNBLOCKED** — authoritative reference INP obtained by
translating an Aspen V14 example over COM (see *Hard dependencies*); clean base via an
isolated worktree. Schema/generator sections below revised to the real keyword format.
**Branch:** a fresh worktree branch off a clean commit (see Constraints)
**Part of:** Process-fidelity upgrade item #2 (LHHW Vanden Bussche–Froment kinetics).
This sub-project (**2a**) builds the *generic* LHHW capability. The VBF96 methanol
parameterization is the separate sub-project **2b**.

## Problem

`process_library/methanol/process.yaml` uses `POWERLAW` reactions with placeholder rate
constants (Eₐ = 0). Real methanol-synthesis kinetics are Langmuir–Hinshelwood–Hougen–Watson
(LHHW): a kinetic factor × a driving-force numerator ÷ an adsorption denominator raised to a
power. The schema (`ReactionParameters`) and generator (`inp_generator.py`) support only
`EQUIL` and `KINETIC` (power-law) — there is **no LHHW support**. 2b (the VBF96 rate law)
cannot exist until the generator can emit LHHW at all.

## Goal (2a scope only)

Add a reusable LHHW reaction capability to the schema, validator, and INP generator so a
spec can declare an LHHW reaction and the generator emits a correct Aspen `REACTIONS … LHHW`
paragraph. **No methanol constants in 2a** — 2a is validated with a generic LHHW reaction
that mirrors the reference INP. VBF96 numbers come in 2b.

## Non-goals

- The VBF96 rate constants / methanol parameterization (that is **2b**).
- Property method / EOS changes (item **#1**, includes adding PSRK).
- Flowsheet changes — H₂ recovery (#3), two-column distillation (#4).
- GLHHW (generalized LHHW) beyond what the reference INP exercises.

## Hard dependencies (both RESOLVED — no user action needed)

1. **Authoritative reference INP — OBTAINED.** Rather than hand-export, Aspen Plus V14
   itself translated its shipped example
   `GUI\Examples\Bulk Chemicals\Methanol\methanol synthesis lab reactor.bkp` into the
   input language via COM `Apwn.Document.Export(4, …)`. Tool: `tools/aspen_bkp_to_inp.py`.
   Result: `docs/superpowers/notes/lhhw_reference.inp` (full deck) and the annotated
   `docs/superpowers/notes/lhhw-keyword-reference.md`. The example's `REACTIONS` paragraph
   exercises every keyword we must emit: two LHHW reactions (RWGS, MEOH-SYN); driving force
   with **both** numerator terms; an adsorption denominator with **4 terms** (`NTERM-ADS=4`)
   and a **power ≠ 1** (reaction 2 uses `ADSORP-POW … EXPONENT=3.`); kinetic factors with
   non-zero activation energy and `T-REF`. Being Aspen-authored, it is correct by
   construction. **Update:** the input language is free-format/token-based, so the generator
   need only emit correct keywords/values/order, not byte-identical whitespace; golden-string
   tests assert on normalized tokens.
2. **Clean base — via worktree, WIP untouched.** The uncommitted WIP in
   `aspen_automation/inp_generator.py` / `tests/unit/test_inp_generator.py` is a *coherent,
   green* feature (directional NRTL `BPVAL` emission) and is left in place. 2a is built in an
   **isolated git worktree off a clean commit**, so it never collides with that WIP and needs
   no commit/stash. Note: the one red test,
   `test_inp_generator.py::test_generate_inp_emits_canonical_methanol_lights_recovery_section`,
   is **committed-red and unrelated** (a `MIX-COL` mixer input-stream-ordering detail in the
   lights-recovery/distillation flowsheet — item #4 territory, not LHHW). LHHW tests are run
   by name so this pre-existing red cannot mask them.

## Confirmed current state (verified)

- `ReactionParameterType` = `EQUIL`, `KINETIC` (`schema.py`). `ReactionParameters` holds
  `phase`, `equilibrium_*`, `rate_basis`, `pre_exponential_factor`, `activation_energy`,
  `temperature_exponent` (`schema.py:844`).
- Generator emits per reaction: `REAC-DATA`, `STOIC`, `K-STOIC` (equil), `RATE-CON`
  (power-law A, Eₐ, n) (`inp_generator.py:836-886`). Reaction-set paragraph header is
  `REACTIONS <id> <block_type>` (`inp_generator.py:852-865`), block_type from
  `reaction_sets[].block_type` (currently `POWERLAW`).
- `VALID_PROPERTY_METHODS` lacks PSRK (relevant only to #1, not 2a).

## Architecture

### Schema (`aspen_automation/schema.py`)

Re-cut to the real keyword axes (see `lhhw-keyword-reference.md`). All nested models
`extra="forbid"`.

- Add `LHHW` to `ReactionParameterType`.
- `LhhwKineticFactor` (→ `RATE-CON`): `pre_exp: float`, `act_energy: float`,
  `act_energy_unit: str = "kcal/mol"`, `t_ref: float | None = None`. (Reference-T Arrhenius
  form `k = k0·exp[−(E/R)(1/T − 1/T_ref)]`. No temperature exponent `n` — absent in the
  canonical deck.)
- `LhhwDrivingForceTerm`: `exponents: dict[str, float]` (component → partial-pressure
  exponent → `DFORCE-EXP` / `DFORCE-EXP-2`) and `coeff: list[float]` (`[A, B, C, D]`,
  trailing zeros omittable, of `K = exp(A + B/T + C·lnT + D·T)` → `DFORCE-EQ-1` /
  `DFORCE-EQ-2`). Term 1's `coeff=[0,…]` ⇒ `K₁=1` (dimensionless), per Aspen convention.
- `LhhwDrivingForce`: `term1: LhhwDrivingForceTerm`, `term2: LhhwDrivingForceTerm`.
- `LhhwAdsorptionTerm` (one per denominator term, `t = 1…NTERM-ADS`):
  `coeff: list[float]` (`[A, B, C, D]` → `ADSORP-EQTER … TERM=t`). The component
  partial-pressure exponents for each term are carried per-component (next field).
- `LhhwAdsorption`: `power: float` (→ `ADSORP-POW … EXPONENT`),
  `terms: list[LhhwAdsorptionTerm]` (length = NTERM-ADS),
  `exponents: dict[str, list[float]]` (component → exponent **vector across the N terms** →
  `ADSORP-EXP … CID=<comp> EXPONENT=<vec>`). `conc_basis: str = "PARTIALPRES"`.
- `ReactionParameters` gains optional `kinetic_factor`, `driving_force`, `adsorption`, plus
  the `REAC-DATA` attributes the deck shows: `conc_basis` (`CBASIS`, default `PARTIALPRES`),
  `rate_basis` (`RBASIS`, default `CAT-WT`), `reversible: bool`, `rev_method`
  (`REV-METH`, default `USER-SPEC`), `pres_unit` (default `BAR`). A `model_validator`
  requires `kinetic_factor`/`driving_force`/`adsorption` present iff
  `reaction_type == LHHW`, and forbids the power-law fields for LHHW.
- `ReactionSet.block_type` gains `GENERAL` (the header Aspen emits for an LHHW/mixed set;
  per-reaction class lives on `REAC-DATA REAC-CLASS=LHHW`). Keep `LHHW` accepted too, but
  the generator emits `GENERAL` to match the reference. A paragraph-level
  `nterm_ads` is derived from the max adsorption-term count (emitted as `PARAM NTERM-ADS`).

### Validator (`aspen_automation/validator.py`)

- For an LHHW reaction: `kinetic_factor`/`driving_force`/`adsorption` all present; both
  driving-force terms present; every `coeff` list has length ≤ 4; adsorption `power > 0`;
  `len(adsorption.terms) == NTERM-ADS` and each component's `adsorption.exponents` vector has
  that same length; every component referenced in any `exponents` map exists in `components`;
  `conc_basis`/`rate_basis`/`rev_method`/`pres_unit` in their allowed sets. Clear, located
  error messages mirroring the existing validation style.

### Generator (`aspen_automation/inp_generator.py`)

- An LHHW/`GENERAL` reaction set emits the paragraph header `REACTIONS <id> GENERAL`
  followed by `PARAM NTERM-ADS=<n>`.
- New `_generate_lhhw_lines(set_id, reactions)` emits, per the transcribed reference format
  (`lhhw-keyword-reference.md`), in this order across the reactions in the set:
  - `REAC-DATA <i> NAME=<n> REAC-CLASS=LHHW PHASE=<p> CBASIS=.. RBASIS=.. REVERSIBLE=..
    REV-METH=.. PRES-UNIT="<u>"`;
  - `RATE-CON <i> PRE-EXP=<k0> ACT-ENERGY=<E> <unit> T-REF=<T0>`;
  - `STOIC <i> MIXED <comp> <coef> / …` (existing stoichiometry emission, reused);
  - `DFORCE-EXP <i> MIXED <comp> <exp> / …` and `DFORCE-EXP-2 <i> …` (term-1/term-2
    exponents);
  - `DFORCE-EQ-1 REACNO=<i> A=.. [B=.. …] / …` and `DFORCE-EQ-2 REACNO=<i> A=.. B=.. / …`
    (term-1/term-2 coefficients), one `REACNO=` group per reaction;
  - `ADSORP-EXP REACNO=<i> CID=<comp> SSID=MIXED EXPONENT=<v1> … <vN> / …`;
  - `ADSORP-EQTER REACNO=<i> TERM=<t> A=.. [B=..] / …`;
  - `ADSORP-POW REACNO=<i> EXPONENT=<p> / …`.
  Activity scaffolding (`ACT-VAL`/`SUBOBJECTS`/`REAC-ACT`) is optional; omit for a
  no-activity model (default) and add only if an activity model is requested.
- Continuation: long `/`-separated lists wrap with ` &`; the generator may choose its own
  wrap width (Aspen is free-format). A small real-number formatter (reuse the existing one)
  renders values.
- `_generate_reactions` routes a set whose reactions are LHHW to `_generate_lhhw_lines`
  instead of the power-law `RATE-CON`-only path.

## Data flow

`process.yaml` LHHW reaction → `load_spec` (schema validates) →
`validate_process_spec_file` (LHHW structural checks) → `generate_inp` emits
`REACTIONS … GENERAL` with per-reaction `REAC-CLASS=LHHW` → **Gate-1 batch translation in
Aspen confirms acceptance** (user-run, or via `tools/aspen_bkp_to_inp.py`'s round-trip).

## Error handling

- Schema/validator reject malformed LHHW (missing terms, wrong coeff length, unknown
  component, non-positive exponent) before generation.
- Generator raises a clear error if an LHHW reaction lacks the required nested parameters
  (should be unreachable after validation, but defensive).

## Testing

- **Headless unit tests** (`tests/unit/test_inp_generator.py` + schema/validator tests):
  given a generic LHHW reaction spec (the one mirrored from the reference INP), assert the
  generated INP block equals the expected keyword block (golden-string match), and that
  schema/validator accept valid LHHW and reject malformed LHHW. These pin the **format**.
- **Aspen acceptance (user):** Gate-1 batch translation of a generated INP containing the
  LHHW reaction must produce a clean `.his` — this is the authoritative confirmation that
  the emitted keywords are Aspen-valid. Cannot be done headlessly without Aspen.

## Validation boundary (explicit)

Claude delivers: the schema/validator/generator capability + headless tests that the
generator emits the **designed** LHHW block (format transcribed from the Aspen-authored
reference INP). The user owns: Gate-1 validating that Aspen accepts the emitted LHHW (and, in
2b, that the VBF96 numbers give credible conversion). The reference INP no longer requires the
user — it was produced by translating an Aspen example over COM. Gate-1 can optionally be
self-checked by round-tripping a generated deck back through `tools/aspen_bkp_to_inp.py`.

## Open items — RESOLVED (reference obtained)

- Exact Aspen keyword spellings/ordering → transcribed in `lhhw-keyword-reference.md`:
  header `REACTIONS <id> GENERAL`; `PARAM NTERM-ADS`; per-reaction
  `REAC-DATA … REAC-CLASS=LHHW`; `RATE-CON`; `DFORCE-EXP`/`DFORCE-EXP-2`;
  `DFORCE-EQ-1`/`DFORCE-EQ-2`; `ADSORP-EXP`/`ADSORP-EQTER`/`ADSORP-POW`.
- Continuation-line rules → free-format; ` &` line continuation; generator chooses its own
  wrapping; golden-string tests assert normalized tokens (not byte-identical whitespace).
- Kinetic factor form → the **reference-T** form (`PRE-EXP` + `ACT-ENERGY <unit>` + `T-REF`);
  no `A·T^n` temperature exponent in the canonical deck.
