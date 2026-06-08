# LHHW Kinetics Capability (2a) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reusable LHHW (Langmuir–Hinshelwood–Hougen–Watson) reaction capability to the schema, validator, and INP generator so a spec can declare an LHHW reaction set and the generator emits a correct Aspen `REACTIONS … GENERAL` paragraph with per-reaction `REAC-CLASS=LHHW` kinetics.

**Architecture:** Additive only. New nested Pydantic models on `ReactionParameters` carry the LHHW rate-law data (kinetic factor, two-term driving force, adsorption denominator). The generator gains a dedicated `_generate_lhhw_reactions(...)` emitter routed from `_generate_reactions` when a set's reactions are LHHW. The validator gains cross-object structural checks (component existence) that the schema cannot see. No methanol constants here — 2a is the generic capability; the VBF96 parameterization is the separate sub-project 2b.

**Tech Stack:** Python 3.12, Pydantic v2 (`ConfigDict(extra="forbid")`, `field_validator`, `model_validator`), pytest. Run tests with `pixi run python -m pytest`.

**Reference:** Keyword format transcribed from Aspen's own export at
`docs/superpowers/notes/lhhw-keyword-reference.md` (and the full deck
`docs/superpowers/notes/lhhw_reference.inp`). The input language is free-format/token-based,
so golden-string tests assert each emitted line as an `in inp` substring — robust to wrapping.

**Important context for the implementer:**
- This runs in the `feature/lhhw-kinetics` worktree, branched off a clean commit.
- One pre-existing test is **committed-red and unrelated**:
  `tests/unit/test_inp_generator.py::test_generate_inp_emits_canonical_methanol_lights_recovery_section`
  (a `MIX-COL` flowsheet detail, not LHHW). **Do not fix it; do not let it block you.** Run
  your new tests by name (`pytest path::test_name -v`), and when running a whole file expect
  that one prior failure to remain.
- `aspen_automation/inp_generator.py` helper `_format_value(x)` renders numbers as
  `str(float(x))` (so `1 → "1.0"`, `0.5 → "0.5"`, `-4.0 → "-4.0"`, `20.0 → "20.0"`). All
  golden strings below use that exact formatting.
- `_wrap_slash_items(prefix, items)` joins items with `" / "` and indents 4 spaces; when the
  prefix ends in a space the first item is appended with no separator. Reuse it for
  `/`-separated lists.
- `_format_stoichiometry_items(reaction)` already yields items like `"CO -1.0"`.

---

## File Structure

- `aspen_automation/schema.py` — add `LHHW` to `ReactionParameterType`; add nested models
  `LhhwKineticFactor`, `LhhwDrivingForceTerm`, `LhhwDrivingForce`, `LhhwAdsorptionTerm`,
  `LhhwAdsorption`; extend `ReactionParameters` with the LHHW fields + `REAC-DATA` attributes;
  extend its `model_validator`.
- `aspen_automation/validator.py` — add LHHW structural checks in the reaction-set loop.
- `aspen_automation/inp_generator.py` — add `_generate_lhhw_reactions(...)` and `_format_coeff(...)`;
  route to it from `_generate_reactions`.
- `tests/unit/test_schema.py` — schema acceptance/rejection tests.
- `tests/unit/test_validator.py` — validator structural tests.
- `tests/unit/test_inp_generator.py` — generator golden-string tests.

---

## Task 1: Schema — LHHW models, fields, and consistency validation

**Files:**
- Modify: `aspen_automation/schema.py` (enum at line 839; `ReactionParameters` at 844–898)
- Test: `tests/unit/test_schema.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/test_schema.py`:

```python
from aspen_automation.schema import (
    ReactionParameters,
    ReactionParameterType,
    LhhwKineticFactor,
    LhhwDrivingForce,
    LhhwDrivingForceTerm,
    LhhwAdsorption,
    LhhwAdsorptionTerm,
)
import pytest
from pydantic import ValidationError as PydanticValidationError


def _valid_lhhw_params() -> dict:
    return {
        "reaction_type": "LHHW",
        "phase": "V",
        "name": "RWGS",
        "kinetic_factor": {"pre_exp": 0.5, "act_energy": 20.0, "t_ref": 500.0},
        "driving_force": {
            "term1": {"exponents": {"CO2": 1.0}, "coeff": [0.0, 0.0]},
            "term2": {"exponents": {"CO": 1.0, "H2O": 1.0, "H2": -1.0}, "coeff": [-4.0, 4000.0]},
        },
        "adsorption": {
            "power": 2.0,
            "terms": [{"coeff": [0.0]}, {"coeff": [8.0, 0.0]}],
            "exponents": {"H2O": [0.0, 1.0]},
        },
    }


def test_lhhw_reaction_parameters_accepts_valid_structure():
    params = ReactionParameters(**_valid_lhhw_params())
    assert params.reaction_type == ReactionParameterType.LHHW
    assert params.kinetic_factor.pre_exp == 0.5
    assert params.kinetic_factor.act_energy_unit == "kcal/mol"  # default
    assert params.driving_force.term2.exponents["H2"] == -1.0
    assert params.adsorption.power == 2.0
    assert len(params.adsorption.terms) == 2


def test_lhhw_requires_all_three_blocks():
    data = _valid_lhhw_params()
    del data["adsorption"]
    with pytest.raises(PydanticValidationError, match="adsorption"):
        ReactionParameters(**data)


def test_lhhw_forbids_power_law_fields():
    data = _valid_lhhw_params()
    data["pre_exponential_factor"] = 1.0
    with pytest.raises(PydanticValidationError, match="not valid for LHHW"):
        ReactionParameters(**data)


def test_non_lhhw_forbids_lhhw_blocks():
    with pytest.raises(PydanticValidationError, match="only valid for LHHW"):
        ReactionParameters(
            reaction_type="KINETIC",
            phase="V",
            pre_exponential_factor=1.0,
            activation_energy=10.0,
            driving_force={
                "term1": {"exponents": {"CO2": 1.0}, "coeff": [0.0]},
                "term2": {"exponents": {"CO": 1.0}, "coeff": [0.0]},
            },
        )


def test_lhhw_adsorption_exponent_vector_length_must_match_terms():
    data = _valid_lhhw_params()
    data["adsorption"]["exponents"] = {"H2O": [0.0, 1.0, 0.0]}  # 3 != 2 terms
    with pytest.raises(PydanticValidationError, match="one per adsorption term"):
        ReactionParameters(**data)


def test_lhhw_coeff_rejects_more_than_four():
    data = _valid_lhhw_params()
    data["driving_force"]["term1"]["coeff"] = [1.0, 2.0, 3.0, 4.0, 5.0]
    with pytest.raises(PydanticValidationError, match="at most 4"):
        ReactionParameters(**data)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pixi run python -m pytest tests/unit/test_schema.py -k lhhw -v`
Expected: FAIL — `ImportError`/`AttributeError` (models don't exist yet).

- [ ] **Step 3: Add the enum value**

In `aspen_automation/schema.py`, extend `ReactionParameterType` (line 839):

```python
class ReactionParameterType(str, enum.Enum):
    EQUIL = "EQUIL"
    KINETIC = "KINETIC"
    LHHW = "LHHW"
```

- [ ] **Step 4: Add the nested LHHW models**

Insert immediately **above** `class ReactionParameters` (before line 844):

```python
class LhhwKineticFactor(BaseModel):
    """Kinetic factor k = k0·exp[-(E/R)(1/T - 1/T_ref)] (reference-T Arrhenius)."""
    model_config = ConfigDict(extra="forbid")
    pre_exp: float
    act_energy: float
    act_energy_unit: str = "kcal/mol"
    t_ref: Optional[float] = None


def _validate_coeff_length(value: List[float]) -> List[float]:
    if len(value) > 4:
        raise ValueError("coeff accepts at most 4 values (A, B, C, D)")
    return value


class LhhwDrivingForceTerm(BaseModel):
    """One driving-force term: Π p_j^exponent times K = exp(A + B/T + C·lnT + D·T)."""
    model_config = ConfigDict(extra="forbid")
    exponents: Dict[str, float] = Field(default_factory=dict)
    coeff: List[float] = Field(default_factory=list)  # [A, B, C, D]; trailing entries omittable

    @field_validator("coeff")
    @classmethod
    def _check_coeff(cls, value: List[float]) -> List[float]:
        return _validate_coeff_length(value)


class LhhwDrivingForce(BaseModel):
    model_config = ConfigDict(extra="forbid")
    term1: LhhwDrivingForceTerm
    term2: LhhwDrivingForceTerm


class LhhwAdsorptionTerm(BaseModel):
    """One adsorption-denominator term coefficient K = exp(A + B/T + C·lnT + D·T)."""
    model_config = ConfigDict(extra="forbid")
    coeff: List[float] = Field(default_factory=list)  # [A, B, C, D]

    @field_validator("coeff")
    @classmethod
    def _check_coeff(cls, value: List[float]) -> List[float]:
        return _validate_coeff_length(value)


class LhhwAdsorption(BaseModel):
    """Adsorption denominator: (Σ_t K_t · Π p_j^exp_{t,j})^power."""
    model_config = ConfigDict(extra="forbid")
    power: float = 1.0
    terms: List[LhhwAdsorptionTerm]
    exponents: Dict[str, List[float]] = Field(default_factory=dict)  # component -> per-term vector
    conc_basis: str = "PARTIALPRES"

    @model_validator(mode="after")
    def _check_vectors(self) -> "LhhwAdsorption":
        n = len(self.terms)
        if n == 0:
            raise ValueError("adsorption.terms must contain at least one term")
        if self.power <= 0:
            raise ValueError("adsorption.power must be positive")
        for component, vector in self.exponents.items():
            if len(vector) != n:
                raise ValueError(
                    f"adsorption.exponents['{component}'] must have {n} values "
                    "(one per adsorption term)"
                )
        return self
```

- [ ] **Step 5: Add LHHW fields to `ReactionParameters`**

In `class ReactionParameters`, after the existing `temperature_exponent` field (line 856) add:

```python
    # LHHW rate-law blocks
    kinetic_factor: Optional[LhhwKineticFactor] = None
    driving_force: Optional[LhhwDrivingForce] = None
    adsorption: Optional[LhhwAdsorption] = None
    # LHHW REAC-DATA attributes (defaults applied at emit time)
    name: Optional[str] = None
    conc_basis: Optional[str] = None
    cat_basis: Optional[str] = None
    reversible: Optional[bool] = None
    rev_method: Optional[str] = None
    pres_unit: Optional[str] = None
```

- [ ] **Step 6: Extend the string-normalizer and the consistency validator**

Add the new string fields to the existing `normalize_string_fields` decorator (line 858) so it reads:

```python
    @field_validator("phase", "equilibrium_form", "equilibrium_basis", "rate_basis",
                     "conc_basis", "cat_basis", "rev_method", "pres_unit")
```

Then, inside `validate_parameter_consistency` (the `model_validator(mode="after")` at line 877), **append** this block just before `return self`:

```python
        if self.reaction_type == ReactionParameterType.LHHW:
            missing = [
                field
                for field, value in (
                    ("kinetic_factor", self.kinetic_factor),
                    ("driving_force", self.driving_force),
                    ("adsorption", self.adsorption),
                )
                if value is None
            ]
            if missing:
                raise ValueError(f"LHHW reactions require: {', '.join(missing)}")
            forbidden = [
                field
                for field, value in (
                    ("pre_exponential_factor", self.pre_exponential_factor),
                    ("activation_energy", self.activation_energy),
                    ("temperature_exponent", self.temperature_exponent),
                    ("rate_basis", self.rate_basis),
                    ("equilibrium_constants", self.equilibrium_constants),
                    ("equilibrium_form", self.equilibrium_form),
                    ("equilibrium_basis", self.equilibrium_basis),
                )
                if value is not None
            ]
            if forbidden:
                raise ValueError(
                    f"These fields are not valid for LHHW reactions: {', '.join(forbidden)}"
                )
        else:
            lhhw_blocks = [
                field
                for field, value in (
                    ("kinetic_factor", self.kinetic_factor),
                    ("driving_force", self.driving_force),
                    ("adsorption", self.adsorption),
                )
                if value is not None
            ]
            if lhhw_blocks:
                raise ValueError(
                    f"{', '.join(lhhw_blocks)} are only valid for LHHW reactions"
                )
```

Note: the existing EQUIL branch raises if `pre_exponential_factor`/`activation_energy` are set,
and the existing KINETIC branch is unchanged. The new block only adds LHHW handling and the
"non-LHHW must not carry LHHW blocks" guard, so it composes cleanly with what's there.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `pixi run python -m pytest tests/unit/test_schema.py -k lhhw -v`
Expected: PASS (6 tests).

- [ ] **Step 8: Run the full schema suite to check for regressions**

Run: `pixi run python -m pytest tests/unit/test_schema.py -q`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add aspen_automation/schema.py tests/unit/test_schema.py
git commit -m "feat(schema): add LHHW reaction parameter models and validation"
```

---

## Task 2: Validator — cross-object LHHW structural checks

**Files:**
- Modify: `aspen_automation/validator.py` (reaction-set loop, around lines 150–210)
- Test: `tests/unit/test_validator.py`

The schema already enforces per-object consistency (presence of blocks, vector lengths). The
validator adds the check it alone can do: every component named in an LHHW reaction's
`driving_force`/`adsorption` exponent maps must exist in `spec.components`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/test_validator.py`:

```python
from aspen_automation.validator import validate_spec


def _lhhw_spec(adsorp_exponents: dict | None = None) -> dict:
    return {
        "metadata": {
            "title": "LHHW",
            "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"},
        },
        "components": [
            {"id": "CO2", "name": "CARBON-DIOXIDE"},
            {"id": "H2", "name": "HYDROGEN"},
            {"id": "CO", "name": "CARBON-MONOXIDE"},
            {"id": "H2O", "name": "WATER"},
        ],
        "properties": {"method": "SRK"},
        "flowsheet": [{"block": "B-SYN", "inputs": ["FEED"], "outputs": ["PROD"]}],
        "streams": [
            {"name": "FEED", "temperature": 220, "pressure": 50, "mass_flow": 1000,
             "composition": {"CO2": 0.25, "H2": 0.75}},
            {"name": "PROD", "temperature": 220, "pressure": 50, "mass_flow": 1000,
             "composition": {"CO2": 0.2, "H2": 0.6, "CO": 0.1, "H2O": 0.1}},
        ],
        "blocks": [
            {"name": "B-SYN", "type": "RPLUG",
             "parameters": {"TEMP": 220, "PRES": 50, "LENGTH": 8.0, "DIAM": 4.0, "NPOINT": 20},
             "reactions": "RXN-LHHW"},
        ],
        "chemistry": [
            {"id": "MEOH-LHHW", "reactions": [
                {"id": 1,
                 "stoichiometry": [
                     {"component": "CO2", "coefficient": -1},
                     {"component": "H2", "coefficient": -1},
                     {"component": "CO", "coefficient": 1},
                     {"component": "H2O", "coefficient": 1}],
                 "parameters": {
                     "reaction_type": "LHHW", "phase": "V", "name": "RWGS",
                     "kinetic_factor": {"pre_exp": 0.5, "act_energy": 20.0, "t_ref": 500.0},
                     "driving_force": {
                         "term1": {"exponents": {"CO2": 1.0}, "coeff": [0.0, 0.0]},
                         "term2": {"exponents": {"CO": 1.0, "H2O": 1.0, "H2": -1.0}, "coeff": [-4.0, 4000.0]}},
                     "adsorption": {
                         "power": 2.0,
                         "terms": [{"coeff": [0.0]}, {"coeff": [8.0, 0.0]}],
                         "exponents": adsorp_exponents if adsorp_exponents is not None else {"H2O": [0.0, 1.0]}}}},
            ]},
        ],
        "reaction_sets": [{"id": "RXN-LHHW", "block_type": "GENERAL", "reaction_ids": [1]}],
    }


def test_validate_accepts_well_formed_lhhw_spec():
    report = validate_spec(_lhhw_spec())
    assert report["valid"], report["errors"]


def test_validate_rejects_lhhw_adsorption_component_not_in_components():
    report = validate_spec(_lhhw_spec(adsorp_exponents={"ARGON": [0.0, 1.0]}))
    assert not report["valid"]
    messages = " ".join(e["message"] for e in report["errors"])
    assert "ARGON" in messages
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pixi run python -m pytest tests/unit/test_validator.py -k lhhw -v`
Expected: `test_validate_accepts_well_formed_lhhw_spec` may pass (no check yet), but
`test_validate_rejects_lhhw_adsorption_component_not_in_components` FAILS (no error raised).

- [ ] **Step 3: Add the LHHW component-existence check**

In `aspen_automation/validator.py`, inside the reaction-set loop (after the REQUIL handling,
within `for j, rxn_id in enumerate(rxn_set.reaction_ids):` where `reaction` is resolved around
line 165), add a sibling branch. First make sure a set of valid component ids is available near
the top of `validate_spec` (reuse the existing one if present; otherwise add):

```python
    component_ids = {c.id for c in spec.components} if spec.components else set()
```

Then within the loop, after the `if not reaction: continue` guard:

```python
                if reaction.parameters and reaction.parameters.reaction_type.value == "LHHW":
                    referenced: set[str] = set()
                    df = reaction.parameters.driving_force
                    if df:
                        referenced.update(df.term1.exponents.keys())
                        referenced.update(df.term2.exponents.keys())
                    ads = reaction.parameters.adsorption
                    if ads:
                        referenced.update(ads.exponents.keys())
                    for component in sorted(referenced):
                        if component_ids and component not in component_ids:
                            add_error(
                                "error",
                                f"{reaction_loc}.parameters",
                                (
                                    f"Component '{component}' used in LHHW reaction '{rxn_id}' "
                                    "but not defined in components"
                                ),
                                "Add the component to the components list or fix the exponent key",
                            )
```

(If `component_ids` is already computed earlier in `validate_spec`, do not redefine it — reuse
the existing variable name.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pixi run python -m pytest tests/unit/test_validator.py -k lhhw -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full validator suite**

Run: `pixi run python -m pytest tests/unit/test_validator.py -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add aspen_automation/validator.py tests/unit/test_validator.py
git commit -m "feat(validator): check LHHW exponent components exist"
```

---

## Task 3: Generator — emit a single-reaction LHHW paragraph

**Files:**
- Modify: `aspen_automation/inp_generator.py` (`_generate_reactions` at 779; add helpers near it)
- Test: `tests/unit/test_inp_generator.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_inp_generator.py`:

```python
def test_generate_inp_emits_lhhw_reaction_block():
    spec = PlantSpecification(**{
        "metadata": {"title": "LHHW",
                     "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}},
        "components": [
            {"id": "CO2", "name": "CARBON-DIOXIDE"},
            {"id": "H2", "name": "HYDROGEN"},
            {"id": "CO", "name": "CARBON-MONOXIDE"},
            {"id": "H2O", "name": "WATER"},
        ],
        "properties": {"method": "SRK"},
        "flowsheet": [{"block": "B-SYN", "inputs": ["FEED"], "outputs": ["PROD"]}],
        "streams": [
            {"name": "FEED", "temperature": 220, "pressure": 50, "mass_flow": 1000,
             "composition": {"CO2": 0.25, "H2": 0.75}},
            {"name": "PROD", "temperature": 220, "pressure": 50, "mass_flow": 1000,
             "composition": {"CO2": 0.2, "H2": 0.6, "CO": 0.1, "H2O": 0.1}},
        ],
        "blocks": [
            {"name": "B-SYN", "type": "RPLUG",
             "parameters": {"TEMP": 220, "PRES": 50, "LENGTH": 8.0, "DIAM": 4.0, "NPOINT": 20},
             "reactions": "RXN-LHHW"},
        ],
        "chemistry": [
            {"id": "MEOH-LHHW", "reactions": [
                {"id": 1,
                 "stoichiometry": [
                     {"component": "CO2", "coefficient": -1},
                     {"component": "H2", "coefficient": -1},
                     {"component": "CO", "coefficient": 1},
                     {"component": "H2O", "coefficient": 1}],
                 "parameters": {
                     "reaction_type": "LHHW", "phase": "V", "name": "RWGS",
                     "kinetic_factor": {"pre_exp": 0.5, "act_energy": 20.0, "t_ref": 500.0},
                     "driving_force": {
                         "term1": {"exponents": {"CO2": 1.0}, "coeff": [0.0, 0.0]},
                         "term2": {"exponents": {"CO": 1.0, "H2O": 1.0, "H2": -1.0},
                                   "coeff": [-4.0, 4000.0]}},
                     "adsorption": {
                         "power": 2.0,
                         "terms": [{"coeff": [0.0]}, {"coeff": [8.0, 0.0]}],
                         "exponents": {"H2O": [0.0, 1.0]}}}},
            ]},
        ],
        "reaction_sets": [{"id": "RXN-LHHW", "block_type": "GENERAL", "reaction_ids": [1]}],
    })

    inp = generate_inp(spec)

    assert "REACTIONS RXN-LHHW GENERAL" in inp
    assert "PARAM NTERM-ADS=2" in inp
    assert ('REAC-DATA 1 NAME=RWGS REAC-CLASS=LHHW PHASE=V CBASIS=PARTIALPRES '
            'RBASIS=CAT-WT REVERSIBLE=YES REV-METH=USER-SPEC PRES-UNIT="BAR"') in inp
    assert "RATE-CON 1 PRE-EXP=0.5 ACT-ENERGY=20.0 <kcal/mol> T-REF=500.0" in inp
    assert "STOIC 1 MIXED CO2 -1.0 / H2 -1.0 / CO 1.0 / H2O 1.0" in inp
    assert "DFORCE-EXP 1 MIXED CO2 1.0" in inp
    assert "DFORCE-EXP-2 1 MIXED CO 1.0 / H2O 1.0 / H2 -1.0" in inp
    assert "DFORCE-EQ-1 REACNO=1 A=0.0 B=0.0" in inp
    assert "DFORCE-EQ-2 REACNO=1 A=-4.0 B=4000.0" in inp
    assert "ADSORP-EXP REACNO=1 CID=H2O SSID=MIXED EXPONENT=0.0 1.0" in inp
    assert "ADSORP-EQTER REACNO=1 TERM=1 A=0.0 / REACNO=1 TERM=2 A=8.0 B=0.0" in inp
    assert "ADSORP-POW REACNO=1 EXPONENT=2.0" in inp
    # LHHW must NOT emit the power-law RATE-CON shorthand or REQUIL K-STOIC
    assert "K-STOIC" not in inp
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pixi run python -m pytest tests/unit/test_inp_generator.py::test_generate_inp_emits_lhhw_reaction_block -v`
Expected: FAIL — the current `_generate_reactions` emits `REACTIONS RXN-LHHW GENERAL` then a
bare `REAC-DATA 1 LHHW …` from the power-law path, missing all LHHW lines.

- [ ] **Step 3: Add the coefficient helper**

In `aspen_automation/inp_generator.py`, near `_generate_reaction_parameter_lines` (after line 813), add:

```python
def _format_coeff(coeff: List[float]) -> str:
    """Render an LHHW coefficient list as 'A=.. B=.. C=.. D=..' for the values provided."""
    labels = ["A", "B", "C", "D"]
    return " ".join(f"{labels[i]}={_format_value(value)}" for i, value in enumerate(coeff))
```

- [ ] **Step 4: Add the LHHW emitter**

Add this function directly below `_format_coeff`:

```python
def _generate_lhhw_reactions(reaction_set: ReactionSet, reaction_lookup: Dict[int, Reaction]) -> str:
    pairs = [(rid, reaction_lookup.get(rid)) for rid in reaction_set.reaction_ids]
    pairs = [(rid, rxn) for rid, rxn in pairs if rxn is not None and rxn.parameters is not None]

    nterm = max(
        (len(rxn.parameters.adsorption.terms) for _, rxn in pairs if rxn.parameters.adsorption),
        default=0,
    )

    lines = [f"REACTIONS {reaction_set.id} GENERAL", f"    PARAM NTERM-ADS={nterm}"]

    # REAC-DATA (one per reaction)
    for rid, rxn in pairs:
        p = rxn.parameters
        reversible = p.reversible if p.reversible is not None else True
        attrs = [f"REAC-DATA {rid}"]
        if p.name:
            attrs.append(f"NAME={p.name}")
        attrs.append("REAC-CLASS=LHHW")
        attrs.append(f"PHASE={p.phase or 'V'}")
        attrs.append(f"CBASIS={p.conc_basis or 'PARTIALPRES'}")
        attrs.append(f"RBASIS={p.cat_basis or 'CAT-WT'}")
        attrs.append(f"REVERSIBLE={'YES' if reversible else 'NO'}")
        attrs.append(f"REV-METH={p.rev_method or 'USER-SPEC'}")
        attrs.append(f'PRES-UNIT="{p.pres_unit or "BAR"}"')
        lines.append("    " + " ".join(attrs))

    # RATE-CON (kinetic factor, one per reaction)
    for rid, rxn in pairs:
        kf = rxn.parameters.kinetic_factor
        parts = [
            f"RATE-CON {rid}",
            f"PRE-EXP={_format_value(kf.pre_exp)}",
            f"ACT-ENERGY={_format_value(kf.act_energy)} <{kf.act_energy_unit}>",
        ]
        if kf.t_ref is not None:
            parts.append(f"T-REF={_format_value(kf.t_ref)}")
        lines.append("    " + " ".join(parts))

    # STOIC (one per reaction)
    for rid, rxn in pairs:
        lines.extend(_wrap_slash_items(f"STOIC {rid} MIXED ", _format_stoichiometry_items(rxn)))

    # DFORCE-EXP / DFORCE-EXP-2 (one per reaction)
    for keyword, attr in (("DFORCE-EXP", "term1"), ("DFORCE-EXP-2", "term2")):
        for rid, rxn in pairs:
            term = getattr(rxn.parameters.driving_force, attr)
            items = [f"MIXED {comp} {_format_value(exp)}" for comp, exp in term.exponents.items()]
            lines.extend(_wrap_slash_items(f"{keyword} {rid} ", items))

    # DFORCE-EQ-1 / DFORCE-EQ-2 (grouped across reactions)
    for keyword, attr in (("DFORCE-EQ-1", "term1"), ("DFORCE-EQ-2", "term2")):
        items = [
            f"REACNO={rid} " + _format_coeff(getattr(rxn.parameters.driving_force, attr).coeff)
            for rid, rxn in pairs
        ]
        lines.extend(_wrap_slash_items(f"{keyword} ", items))

    # ADSORP-EXP (grouped: per reaction, per component)
    ads_exp_items = [
        f"REACNO={rid} CID={comp} SSID=MIXED EXPONENT="
        + " ".join(_format_value(x) for x in vector)
        for rid, rxn in pairs
        for comp, vector in rxn.parameters.adsorption.exponents.items()
    ]
    lines.extend(_wrap_slash_items("ADSORP-EXP ", ads_exp_items))

    # ADSORP-EQTER (grouped: per reaction, per term)
    eqter_items = [
        f"REACNO={rid} TERM={t} " + _format_coeff(term.coeff)
        for rid, rxn in pairs
        for t, term in enumerate(rxn.parameters.adsorption.terms, start=1)
    ]
    lines.extend(_wrap_slash_items("ADSORP-EQTER ", eqter_items))

    # ADSORP-POW (grouped)
    pow_items = [
        f"REACNO={rid} EXPONENT={_format_value(rxn.parameters.adsorption.power)}"
        for rid, rxn in pairs
    ]
    lines.extend(_wrap_slash_items("ADSORP-POW ", pow_items))

    return "\n".join(lines)
```

- [ ] **Step 5: Route LHHW sets to the new emitter**

In `_generate_reactions` (line 779), after computing `block_type` and the `REQUIL` early
return, add a routing check before the existing power-law loop:

```python
def _generate_reactions(reaction_set: ReactionSet, reaction_lookup: Dict[int, Reaction]) -> str:
    block_type = reaction_set.block_type.upper()
    if block_type == "REQUIL":
        return ""

    if _set_is_lhhw(reaction_set, reaction_lookup):
        return _generate_lhhw_reactions(reaction_set, reaction_lookup)

    lines = [f"REACTIONS {reaction_set.id} {block_type}"]
    # ... existing power-law loop unchanged ...
```

And add the predicate near the top of the reaction helpers (e.g. above `_generate_reactions`):

```python
def _set_is_lhhw(reaction_set: ReactionSet, reaction_lookup: Dict[int, Reaction]) -> bool:
    for rid in reaction_set.reaction_ids:
        reaction = reaction_lookup.get(rid)
        params = reaction.parameters if reaction else None
        if params and params.reaction_type == ReactionParameterType.LHHW:
            return True
    return False
```

Ensure `ReactionParameterType` is imported in `inp_generator.py` (it imports from `.schema`;
add it to that import if not already present).

- [ ] **Step 6: Run the test to verify it passes**

Run: `pixi run python -m pytest tests/unit/test_inp_generator.py::test_generate_inp_emits_lhhw_reaction_block -v`
Expected: PASS.

- [ ] **Step 7: Run the generator suite (expect only the known pre-existing failure)**

Run: `pixi run python -m pytest tests/unit/test_inp_generator.py -q`
Expected: all pass **except** the one known committed-red test
(`test_generate_inp_emits_canonical_methanol_lights_recovery_section`). Confirm your new test
passes and no *other* test regressed.

- [ ] **Step 8: Commit**

```bash
git add aspen_automation/inp_generator.py tests/unit/test_inp_generator.py
git commit -m "feat(generator): emit LHHW reaction paragraph"
```

---

## Task 4: Generator — multi-reaction grouping and NTERM-ADS = max

**Files:**
- Test: `tests/unit/test_inp_generator.py`
- (No production change expected — this verifies the grouping logic from Task 3.)

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_inp_generator.py`:

```python
def test_generate_inp_groups_multiple_lhhw_reactions():
    def lhhw(name, stoich, power, df2_coeff):
        return {
            "reaction_type": "LHHW", "phase": "V", "name": name,
            "kinetic_factor": {"pre_exp": 1.0, "act_energy": 10.0, "t_ref": 500.0},
            "driving_force": {
                "term1": {"exponents": {"CO2": 1.0}, "coeff": [0.0, 0.0]},
                "term2": {"exponents": {"H2": -1.0}, "coeff": df2_coeff}},
            "adsorption": {
                "power": power,
                "terms": [{"coeff": [0.0]}, {"coeff": [8.0, 0.0]}],
                "exponents": {"H2O": [0.0, 1.0]}},
        }

    spec = PlantSpecification(**{
        "metadata": {"title": "LHHW2",
                     "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}},
        "components": [
            {"id": "CO2", "name": "CARBON-DIOXIDE"}, {"id": "H2", "name": "HYDROGEN"},
            {"id": "CO", "name": "CARBON-MONOXIDE"}, {"id": "H2O", "name": "WATER"},
            {"id": "CH3OH", "name": "METHANOL"},
        ],
        "properties": {"method": "SRK"},
        "flowsheet": [{"block": "B-SYN", "inputs": ["FEED"], "outputs": ["PROD"]}],
        "streams": [
            {"name": "FEED", "temperature": 220, "pressure": 50, "mass_flow": 1000,
             "composition": {"CO2": 0.25, "H2": 0.75}},
            {"name": "PROD", "temperature": 220, "pressure": 50, "mass_flow": 1000,
             "composition": {"CO2": 0.2, "H2": 0.5, "CO": 0.1, "H2O": 0.1, "CH3OH": 0.1}},
        ],
        "blocks": [
            {"name": "B-SYN", "type": "RPLUG",
             "parameters": {"TEMP": 220, "PRES": 50, "LENGTH": 8.0, "DIAM": 4.0, "NPOINT": 20},
             "reactions": "RXN-LHHW"},
        ],
        "chemistry": [
            {"id": "MEOH-LHHW", "reactions": [
                {"id": 1, "stoichiometry": [
                    {"component": "CO2", "coefficient": -1}, {"component": "H2", "coefficient": -1},
                    {"component": "CO", "coefficient": 1}, {"component": "H2O", "coefficient": 1}],
                 "parameters": lhhw("RWGS", None, 2.0, [-4.0, 4000.0])},
                {"id": 2, "stoichiometry": [
                    {"component": "CO2", "coefficient": -1}, {"component": "H2", "coefficient": -3},
                    {"component": "CH3OH", "coefficient": 1}, {"component": "H2O", "coefficient": 1}],
                 "parameters": lhhw("MEOH", None, 3.0, [10.0, -9000.0])},
            ]},
        ],
        "reaction_sets": [{"id": "RXN-LHHW", "block_type": "GENERAL", "reaction_ids": [1, 2]}],
    })

    inp = generate_inp(spec)

    assert "REAC-DATA 1 NAME=RWGS REAC-CLASS=LHHW" in inp
    assert "REAC-DATA 2 NAME=MEOH REAC-CLASS=LHHW" in inp
    assert "DFORCE-EQ-1 REACNO=1 A=0.0 B=0.0 / REACNO=2 A=0.0 B=0.0" in inp
    assert "DFORCE-EQ-2 REACNO=1 A=-4.0 B=4000.0 / REACNO=2 A=10.0 B=-9000.0" in inp
    assert "ADSORP-POW REACNO=1 EXPONENT=2.0 / REACNO=2 EXPONENT=3.0" in inp
    # PARAM NTERM-ADS is the max term count across reactions (both 2 here)
    assert "PARAM NTERM-ADS=2" in inp
```

- [ ] **Step 2: Run the test**

Run: `pixi run python -m pytest tests/unit/test_inp_generator.py::test_generate_inp_groups_multiple_lhhw_reactions -v`
Expected: PASS if Task 3 was implemented correctly. If it FAILS, fix `_generate_lhhw_reactions`
(grouping/ordering) until it passes — do not change the test.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_inp_generator.py
git commit -m "test(generator): cover multi-reaction LHHW grouping"
```

---

## Task 5: Round-trip sanity + suite check

**Files:**
- Test: `tests/unit/test_inp_generator.py`

- [ ] **Step 1: Write the failing test (structural well-formedness)**

Add a test that the emitted LHHW block has the keyword paragraphs in the reference order, so a
future refactor can't silently reorder them:

```python
def test_lhhw_block_keyword_order_matches_reference():
    spec = PlantSpecification(**{
        "metadata": {"title": "LHHW",
                     "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}},
        "components": [
            {"id": "CO2", "name": "CARBON-DIOXIDE"}, {"id": "H2", "name": "HYDROGEN"},
            {"id": "CO", "name": "CARBON-MONOXIDE"}, {"id": "H2O", "name": "WATER"}],
        "properties": {"method": "SRK"},
        "flowsheet": [{"block": "B-SYN", "inputs": ["FEED"], "outputs": ["PROD"]}],
        "streams": [
            {"name": "FEED", "temperature": 220, "pressure": 50, "mass_flow": 1000,
             "composition": {"CO2": 0.25, "H2": 0.75}},
            {"name": "PROD", "temperature": 220, "pressure": 50, "mass_flow": 1000,
             "composition": {"CO2": 0.2, "H2": 0.6, "CO": 0.1, "H2O": 0.1}}],
        "blocks": [
            {"name": "B-SYN", "type": "RPLUG",
             "parameters": {"TEMP": 220, "PRES": 50, "LENGTH": 8.0, "DIAM": 4.0, "NPOINT": 20},
             "reactions": "RXN-LHHW"}],
        "chemistry": [
            {"id": "MEOH-LHHW", "reactions": [
                {"id": 1, "stoichiometry": [
                    {"component": "CO2", "coefficient": -1}, {"component": "H2", "coefficient": -1},
                    {"component": "CO", "coefficient": 1}, {"component": "H2O", "coefficient": 1}],
                 "parameters": {
                     "reaction_type": "LHHW", "phase": "V", "name": "RWGS",
                     "kinetic_factor": {"pre_exp": 0.5, "act_energy": 20.0, "t_ref": 500.0},
                     "driving_force": {
                         "term1": {"exponents": {"CO2": 1.0}, "coeff": [0.0, 0.0]},
                         "term2": {"exponents": {"CO": 1.0, "H2O": 1.0, "H2": -1.0}, "coeff": [-4.0, 4000.0]}},
                     "adsorption": {"power": 2.0, "terms": [{"coeff": [0.0]}, {"coeff": [8.0, 0.0]}],
                                    "exponents": {"H2O": [0.0, 1.0]}}}}]}],
        "reaction_sets": [{"id": "RXN-LHHW", "block_type": "GENERAL", "reaction_ids": [1]}],
    })

    inp = generate_inp(spec)
    order = ["REACTIONS RXN-LHHW GENERAL", "PARAM NTERM-ADS=", "REAC-DATA 1", "RATE-CON 1",
             "STOIC 1 MIXED", "DFORCE-EXP 1", "DFORCE-EXP-2 1", "DFORCE-EQ-1", "DFORCE-EQ-2",
             "ADSORP-EXP", "ADSORP-EQTER", "ADSORP-POW"]
    positions = [inp.index(token) for token in order]
    assert positions == sorted(positions), "LHHW keyword paragraphs are out of reference order"
```

- [ ] **Step 2: Run it**

Run: `pixi run python -m pytest tests/unit/test_inp_generator.py::test_lhhw_block_keyword_order_matches_reference -v`
Expected: PASS.

- [ ] **Step 3: Run the entire unit suite**

Run: `pixi run python -m pytest tests/unit -q`
Expected: only the single known committed-red test fails
(`test_generate_inp_emits_canonical_methanol_lights_recovery_section`). Everything else passes.
If any *other* test fails, fix the cause before continuing.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_inp_generator.py
git commit -m "test(generator): pin LHHW keyword paragraph order"
```

---

## Self-Review (completed during planning)

- **Spec coverage:** schema models (Task 1) ↔ spec "Schema"; validator checks (Task 2) ↔ spec
  "Validator"; generator emitter + routing (Tasks 3–4) ↔ spec "Generator"; keyword order/format
  (Tasks 3–5) ↔ `lhhw-keyword-reference.md`. The Gate-1 Aspen acceptance remains the user's (or
  a `tools/aspen_bkp_to_inp.py` round-trip) — out of scope for headless tests, per the spec.
- **Type consistency:** field/method names are consistent across tasks — `kinetic_factor`,
  `driving_force` (`term1`/`term2`, `exponents`, `coeff`), `adsorption` (`power`, `terms`,
  `exponents`, `conc_basis`), `pre_exp`/`act_energy`/`act_energy_unit`/`t_ref`,
  `_generate_lhhw_reactions`, `_format_coeff`, `_set_is_lhhw`.
- **Golden strings** use `_format_value` output (`str(float)`) and `_wrap_slash_items` ` / `
  joining; verified against the helper behavior in `inp_generator.py`.
- **Known red test** is called out in every suite-run step so it cannot be mistaken for a
  regression.

## Out of scope (do NOT do here)

- The VBF96 methanol constants / wiring `process.yaml` to LHHW (that is 2b).
- Property-method/EOS changes (item #1), H₂ recovery (item #3), two-column distillation (item #4).
- Fixing the committed-red `…lights_recovery_section` test (item #4 territory).
