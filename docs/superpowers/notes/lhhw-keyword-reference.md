# Aspen LHHW input-language keyword reference

**Provenance.** Translated by Aspen Plus V14 itself from the shipped example
`...\Aspen Plus V14.0\GUI\Examples\Bulk Chemicals\Methanol\methanol synthesis lab reactor.bkp`
via COM `Apwn.Document.Export(4, …)` (format code 4 = input language). Tool:
[tools/aspen_bkp_to_inp.py](../../../tools/aspen_bkp_to_inp.py). Full deck:
[lhhw_reference.inp](lhhw_reference.inp) (the `REACTIONS` paragraph is lines 855–908).

This file is the **authoritative** source for the keyword spellings/ordering the
generator must emit (resolves the "open items" the design spec deferred to a
reference INP). It is Aspen-authored, so it is correct by construction.

## The reactions paragraph (verbatim)

```
REACTIONS MEOH-SYN GENERAL
    PARAM NTERM-ADS=4
    REAC-DATA 1 NAME=RWGS REAC-CLASS=LHHW PHASE=V  &
        CBASIS=PARTIALPRES RBASIS=CAT-WT REVERSIBLE=YES  &
        REV-METH=USER-SPEC PRES-UNIT="BAR"
    REAC-DATA 2 NAME=MEOH-SYN REAC-CLASS=LHHW PHASE=V  &
        CBASIS=PARTIALPRES RBASIS=CAT-WT REVERSIBLE=YES  &
        REV-METH=USER-SPEC PRES-UNIT="BAR"
    RATE-CON 1 PRE-EXP=0.00165 ACT-ENERGY=22.6342 <kcal/mol>  &
        T-REF=228.42
    RATE-CON 2 PRE-EXP=7.07034 ACT-ENERGY=-8.76469 <kcal/mol>  &
        T-REF=228.4200000
    STOIC 1 MIXED CO2 -1. / H2 -1. / CO 1. / H2O 1.
    STOIC 2 MIXED CO2 -1. / H2 -3. / MEOH 1. / H2O 1.
    DFORCE-EXP 1 MIXED CO2 1.
    DFORCE-EXP 2 MIXED CO2 1. / MIXED H2 1.
    DFORCE-EXP-2 1 MIXED H2 -1. / MIXED CO 1. / MIXED H2O 1.
    DFORCE-EXP-2 2 MIXED H2 -2. / MIXED MEOH 1. / MIXED H2O 1.
    DFORCE-EQ-1 REACNO=1 A=0. B=0. / REACNO=2 A=0.
    DFORCE-EQ-2 REACNO=1 A=-4.671945154 B=4773.258898 /  &
        REACNO=2 A=24.3889813 B=-7059.72589
    ADSORP-EXP REACNO=1 CID=H2O SSID=MIXED EXPONENT=0. 1. 0. 1. /  &
        REACNO=1 CID=H2 SSID=MIXED EXPONENT=0. -1. 0.5 0. /  &
        REACNO=2 CID=H2O SSID=MIXED EXPONENT=0. 1. 0. 1. /  &
        REACNO=2 CID=H2 SSID=MIXED EXPONENT=0. -1. 0.5 0.
    ADSORP-EQTER REACNO=1 TERM= 1 A=0. / REACNO=1 TERM= 2  &
        A=8.147108741 B=0. / REACNO=1 TERM= 3 A=-0.6951  &
        B=2068.3 / REACNO=1 TERM= 4 A=-23.438 B=14928.19686 /  &
        REACNO=2 TERM= 1 A=0. / REACNO=2 TERM= 2 A=8.147108741  &
        B=0. / REACNO=2 TERM= 3 A=-0.69515 B=2068.3 /  &
        REACNO=2 TERM= 4 A=-23.43827453 B=14928.19686
    ADSORP-POW REACNO=1 EXPONENT=1. / REACNO=2 EXPONENT=3.
    ACT-VAL ACTIVITY
    SUBOBJECTS ACTIVITY = ACTIVITY
    REAC-ACT 1 ACTIVITY=ACTIVITY / 2 ACTIVITY=ACTIVITY
```

(Reactions 3/4 — `F-ETOH`, `DME-FORM` — are `POWERLAW` side reactions in the
original example and are omitted here; our methanol model is the 2-reaction
RWGS + MEOH-SYN subset.)

## Keyword semantics — mapping to the LHHW rate law

For reaction *i*: `rate = k · (driving force) / (adsorption)^power`.

| Keyword | Meaning |
|---|---|
| `REACTIONS <id> GENERAL` | Reaction-set header. `GENERAL` (not `LHHW`) when the set mixes classes; per-reaction class is set on `REAC-DATA`. A pure-LHHW set may also use `GENERAL`; this is the Aspen-proven choice. |
| `PARAM NTERM-ADS=<n>` | Paragraph-level: number of terms in the adsorption denominator (here 4). |
| `REAC-DATA <i> NAME=<n> REAC-CLASS=LHHW PHASE=V CBASIS=PARTIALPRES RBASIS=CAT-WT REVERSIBLE=YES REV-METH=USER-SPEC PRES-UNIT="BAR"` | Per-reaction header. `CBASIS=PARTIALPRES` → concentration basis is partial pressure; `RBASIS=CAT-WT` → rate per catalyst weight; `REV-METH=USER-SPEC` → equilibrium supplied via `DFORCE-EQ-2`. |
| `RATE-CON <i> PRE-EXP=<k0> ACT-ENERGY=<E> <kcal/mol> T-REF=<T0>` | Kinetic factor `k = k0·exp[−(E/R)(1/T − 1/T0)]` (reference-temperature Arrhenius). Note the inline unit token `<kcal/mol>`. **No `n` (temperature exponent) in this canonical form.** |
| `STOIC <i> MIXED <comp> <coef> / …` | Stoichiometry (substream `MIXED`). |
| `DFORCE-EXP <i> MIXED <comp> <exp> / …` | Exponents of the **first** driving-force term (forward group): `Π p_j^exp`. |
| `DFORCE-EXP-2 <i> MIXED <comp> <exp> / …` | Exponents of the **second** driving-force term (reverse/equilibrium group). |
| `DFORCE-EQ-1 REACNO=<i> A=.. B=.. [C=.. D=..] / …` | Coefficients of term-1 constant `K1 = exp(A + B/T + C·lnT + D·T)`. Here `A=B=0` → `K1=1` (dimensionless), per Aspen's LHHW convention. |
| `DFORCE-EQ-2 REACNO=<i> A=.. B=.. / …` | Coefficients of term-2 constant `K2` (the equilibrium group). |
| `ADSORP-EXP REACNO=<i> CID=<comp> SSID=MIXED EXPONENT=<e1> <e2> … <eN> / …` | For (reaction, component): the exponent of that component in **each** of the N adsorption terms (vector length `NTERM-ADS`). |
| `ADSORP-EQTER REACNO=<i> TERM=<t> A=.. [B=..] / …` | Coefficient of adsorption term *t*: `Kt = exp(A + B/T + …)`. Term 1 here is `A=0` → the constant `1`. |
| `ADSORP-POW REACNO=<i> EXPONENT=<p> / …` | Denominator power *p*. **Reaction 2 uses `EXPONENT=3.` — the required power≠1 case.** |
| `ACT-VAL` / `SUBOBJECTS` / `REAC-ACT` | Catalyst-activity scaffolding; constant `ACTIVITY`. Can be emitted as-is or omitted for a no-activity model. |

## Format notes that de-risk the generator

- **The input language is free-format and token-based.** Continuation is ` &`
  at end of line; Aspen does not care about exact column alignment or whether a
  list is wrapped. The generator may emit its own clean wrapping; **golden-string
  tests should assert on normalized tokens/keywords, not byte-identical
  whitespace.** This removes the "byte-accurate" risk the spec worried about.
- Numbers print as Aspen reals (`-1.`, `0.5`, `1E-012`). The generator's existing
  real-formatting helper is adequate; trailing `.` is optional to Aspen.
- Inline unit tokens use angle brackets: `ACT-ENERGY=22.6342 <kcal/mol>`,
  `T-REF=228.42`. T-REF carries no unit here (defaults to the deck temperature unit).

## How this diverges from the original design spec (to reconcile)

1. Header is `REACTIONS <id> GENERAL`, **not** `REACTIONS <id> LHHW`. LHHW is a
   per-reaction `REAC-CLASS` on `REAC-DATA`.
2. Kinetic factor is the **reference-T** form (`PRE-EXP`/`ACT-ENERGY`/`T-REF`),
   not `A·T^n·exp(−E/RT)`. The spec's `n` field is unused in the canonical deck.
3. Driving force is **two pairs** of paragraphs: exponents (`DFORCE-EXP`,
   `DFORCE-EXP-2`) separate from temperature coefficients (`DFORCE-EQ-1`,
   `DFORCE-EQ-2` keyed by `REACNO`, fields `A/B[/C/D]`). The spec's single
   `LhhwTerm {coeff[4], exponents{}}` must split into an exponents map + an
   `A/B/C/D` coefficient group.
4. Adsorption is organized as **per-(reaction,component) exponent vectors**
   (`ADSORP-EXP … EXPONENT=<vec>`) plus **per-(reaction,term) coefficients**
   (`ADSORP-EQTER`) plus a **per-reaction power** (`ADSORP-POW`), with the term
   count hoisted to `PARAM NTERM-ADS`. The spec's `LhhwAdsorption.terms[]` shape
   should be re-cut along these axes.
