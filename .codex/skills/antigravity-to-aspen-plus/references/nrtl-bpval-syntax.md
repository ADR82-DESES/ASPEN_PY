# Directional NRTL `BPVAL` Syntax in Generated INP

This is the exact rule the `inp_generator` follows when emitting explicit NRTL binary
parameters (`source_type: explicit`). Getting it wrong silently produces garbage activity
coefficients while still translating and converging — so it is worth stating precisely.

## The rule: `BPVAL` is directional, one line per direction

Aspen's NRTL `BPVAL` fills parameter slots **positionally** and **per direction**:

- `BPVAL c1 c2 v1 v2 v3 v4 v5 v6` fills only the **forward (i→j)** elements as
  `[aij, bij, cij, dij, eij, fij]`.
- The **reverse (j→i)** elements need a **second line with the components swapped**:
  `BPVAL c2 c1 …` fills `[aji, bji, cij, dij, eji, fji]`.

So forward and reverse `a` and `b` go on **different lines**. `cij` (the NRTL α) is
symmetric and appears in slot 3 of the forward line.

### Correct output (verified)

```
PROP-DATA NRTL-1
    PROP-LIST NRTL
    BPVAL CH3OH H2O -0.69201 172.6353 0.3
    BPVAL H2O CH3OH 2.73113 -616.882
```

- Forward line `CH3OH H2O`: `aij=-0.69201`, `bij=172.6353`, `cij(α)=0.3`.
- Reverse line `H2O CH3OH`: `aji=2.73113`, `bji=-616.882`.

Reading it back from the `.bkp`, the user values land in **`UVAL1..UVAL5`**
(= `aij, aji, bij, bji, cij`), **not** `VAL*`. User-entered parameters live in `UVAL*`
nodes; `VAL*` are the databank/internal slots. Verified γ = **1.1323 / 1.1909**.

## The bug this fixes

The original emitter wrote all five values on **one line**:
`BPVAL c1 c2 aij aji bij bji cij`. Because `BPVAL` is positional/forward, that mapped:

- `aji` → `bij` slot
- `bij` → `cij(α)` slot → α = 172 (insane), etc.

Result: γ ≈ 2.48 / 2.90 instead of ~1.13 / 1.19, and product purity collapsed
(e.g. 99.89% → 94.87%) while the run still "converged." The two-line directional form is
the fix.

> The `NRTL-1` dataset-name "collision" was a **red herring** — Aspen normalizes the
> dataset name and it never mattered. The real cause was the single-line element mapping.

## Emitter contract

`inp_generator._generate_binary_parameters` emits the two-line directional form. The
relevant constants:

```python
NRTL_BPVAL_FORWARD_ORDER = ["aij", "bij", "cij", "dij", "eij", "fij"]
NRTL_BPVAL_REVERSE_ORDER = ["aji", "bji", "cij", "dij", "eji", "fji"]
NRTL_UNSUPPORTED_EXPLICIT_FIELDS = ("t_lower", "t_upper")
```

- Trailing zero-valued slots are trimmed so the lines stay short (helpers
  `_format_param_value`, `_trim_trailing_zeros`).
- `source_type: explicit` is accepted; the `_validate_generator_compatibility` guard now
  rejects **only** `t_lower`/`t_upper` (temperature limits are not yet emittable as
  `BPVAL` and would need `BPVAL … TLOWER/TUPPER` qualifiers).

## YAML shape

```yaml
binary_parameters:
  - components: [CH3OH, H2O]
    model: NRTL
    source_type: explicit
    values:
      aij: -0.69201
      aji: 2.73113
      bij: 172.6353
      bji: -616.882
      cij: 0.3
    # provenance: recovered via activity-coefficient calibration; see
    # binary-parameter-calibration.md
```

## How to verify after a change

1. Regenerate INP, run Gate 1.
2. Open the `.bkp` and confirm `UVAL1..UVAL5 = aij, aji, bij, bji, cij`.
3. Run a γ probe at a known (T, x) and confirm γ matches the calibration (≈1.13/1.19 for
   methanol–water), **not** 2.4/2.9.
4. Confirm the end-to-end capsule reports `nrtl…=provided`, `warnings=[]`, and product
   purity matches the databank result.
