# LHHW Kinetics Capability (2a) — Design

**Date:** 2026-06-08
**Status:** Approved (design); BLOCKED on two user inputs before implementation
**Branch:** `feature/run-dashboard` (or a fresh branch off a clean base — see Constraints)
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

## Hard dependencies (implementation is BLOCKED until both are satisfied)

1. **Authoritative reference INP.** The generator must emit **byte-accurate** Aspen LHHW
   keywords; the exact input-language syntax is not publicly documented. The user exports a
   minimal reference `.inp` from Aspen containing **one LHHW reaction** that exercises every
   keyword we must emit:
   - an RPLUG (or RCSTR) block with one LHHW kinetic reaction;
   - a **driving-force** with **both** numerator terms (forward + equilibrium term);
   - an **adsorption** denominator with **≥2 terms** (the constant `1` term plus ≥2
     partial-pressure-dependent terms) and a **power ≠ 1** (2 or 3);
   - a **kinetic factor** with non-zero E and n.
   The generator mirrors this file's keyword format exactly. Components are irrelevant — only
   the keyword *format* is consumed.
2. **Clean `inp_generator.py`.** `aspen_automation/inp_generator.py` and
   `tests/unit/test_inp_generator.py` carry the user's uncommitted WIP. The user
   commits/stashes it first so 2a branches from a clean base (avoids clobber/merge friction).

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

- Add `LHHW` to `ReactionParameterType`.
- New nested models (all `extra="forbid"`):
  - `LhhwKineticFactor`: `a: float` (pre-exponential), `e: float` (activation energy),
    `n: float = 0.0`, `t0: float | None = None` (reference T).
  - `LhhwTerm`: `coeff: list[float]` (exactly 4 → A,B,C,D of `exp(A + B/T + C·lnT + D·T)`),
    `exponents: dict[str, float]` (component → concentration exponent; may be empty for the
    constant `1` term).
  - `LhhwDrivingForce`: `basis: str` (e.g. `PARTIAL`), `term1: LhhwTerm`, `term2: LhhwTerm`
    (term 2 is the equilibrium group; per Aspen, K₁ is dimensionless).
  - `LhhwAdsorption`: `basis: str`, `exponent: float` (denominator power), `terms:
    list[LhhwTerm]` (≥1; first is typically the `1` term with `coeff=[0,0,0,0]`,
    `exponents={}`).
- Extend `ReactionParameters` with optional `kinetic_factor`, `driving_force`,
  `adsorption`. A `model_validator` requires all three present iff
  `reaction_type == LHHW`, and forbids the power-law fields (`pre_exponential_factor`,
  `activation_energy`) for LHHW.
- `ReactionSet.block_type` gains `LHHW` as an allowed value.

### Validator (`aspen_automation/validator.py`)

- For an LHHW reaction: both driving-force terms present; each `coeff` length 4; ≥1
  adsorption term; `exponent > 0`; every component referenced in any `exponents` map exists
  in `components`; `basis` in an allowed set. Clear, located error messages mirroring the
  existing validation style.

### Generator (`aspen_automation/inp_generator.py`)

- `block_type == "LHHW"` → emit `REACTIONS <id> LHHW`.
- New `_generate_lhhw_lines(rxn_id, params)` emitting, **in the reference file's exact
  keyword spelling/order** (placeholders below are the *intended* shape; final keywords are
  transcribed from the reference INP):
  - kinetic factor (`K <id> A E n [T0]`-style line);
  - driving-force exponents + coefficient lines for term 1 and term 2, with the basis;
  - adsorption term exponents + coefficient lines for each term, the basis, and the
    denominator power.
- `_generate_reactions` routes LHHW reactions to `_generate_lhhw_lines` instead of the
  power-law `RATE-CON` path; `STOIC` emission is unchanged.

## Data flow

`process.yaml` LHHW reaction → `load_spec` (schema validates) →
`validate_process_spec_file` (LHHW structural checks) → `generate_inp` emits
`REACTIONS … LHHW` → **Gate-1 batch translation in Aspen confirms acceptance** (user-run).

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
generator emits the **designed** LHHW block (format derived from the user's reference INP).
The user owns: exporting the reference INP, and Gate-1 validating that Aspen accepts the
emitted LHHW (and, in 2b, that the VBF96 numbers give credible conversion).

## Open items resolved during implementation

- Exact Aspen keyword spellings/ordering and any continuation-line rules → transcribed from
  the reference INP.
- Whether the kinetic factor uses the (1/T − 1/T₀) form (T₀ given) or A·T^n·exp(−E/RT)
  (no T₀) → matched to the reference.
