# COM-Launched Aspen Under AppsAnywhere/Cloudpaging Virtualization

## The problem this explains

A batch-first capsule can pass Gate 1 cleanly (the Aspen batch translator produces a
good `.bkp`) and still emit, in its post-COM history:

```
NRTL BINARY PARAMETERS FOR ALL COMPONENT PAIRS ARE ZERO
```

This is **not** a `.bkp` databank-reversion bug, a `PROP-SOURCES`/`DATABANKS` ordering
bug, or a load-mechanism bug. It is an environment property of the virtualized COM
context.

## Root cause (verified by live probes)

There are two different Aspen engines in this stack:

- **External batch engine** (`aspenbatch`, used in Gate 1) — runs in the real install
  and **does** retrieve binary interaction parameters from the
  `APV140` VLE-IG / VLE-LIT / LLE-ASPEN databanks.
- **COM-launched engine** (`Apwn.Document` via `DispatchEx`, used in Gate 2) — runs
  inside the **AppsAnywhere/Cloudpaging sandbox** and does **not** retrieve those
  databank parameters.

The warning appears on **every** COM load path — both `InitFromArchive2(.bkp)` and
`InitFromFile2(INP)` — confirming it is not tied to a particular load entry point.

### Corroborating evidence to collect

The capsule's `context_probe.json` is built for exactly this escalation. Look for:

- `suspected_appanywhere_virtualization: true`
- The COM context cannot load `AspenTech.AspenPlus.Localization`
  ("El sistema no puede encontrar el archivo" / "The system cannot find the file").
- AppsAnywhere/Cloudpaging package markers in the process ancestry.

The sandbox is missing parts of the install, including functional VLE databank access.

## Why you can't fix it COM-side

- **No settable databank-selection node.** There is no editable search-order list in the
  COM tree. Searched `\Data\Components\Specifications` and `\Data\Properties`; only
  per-component `DBNAME` lookup names exist — no databank search order to re-apply.
- **Databank-retrieved values are not readable from the COM tree.**
  `\Data\Properties\Parameters\Binary Interaction\NRTL-1\Input\VAL1..VAL12` are all
  `None`. Databank parameters live in the engine internals and never populate the
  editable tree — which is also why they can't persist into the `.bkp`.
- Even an INP with an explicit `DATABANKS` paragraph, loaded via `InitFromFile2`, still
  warns. The retrieval, not the selection, is what's broken under virtualization.

## The only code-level fix

Bake **explicit numeric binary parameters** into the model so retrieval is never needed.
The schema supports `source_type: explicit` + `values` on a binary parameter; the
`inp_generator` emits a `PROP-DATA/BPVAL` paragraph that the COM engine reads directly.

See [nrtl-bpval-syntax.md](nrtl-bpval-syntax.md) for the exact directional emitter, and
[binary-parameter-calibration.md](binary-parameter-calibration.md) for how to recover the
real coefficient values when you don't have them from a GUI.

## When to escalate to IT instead

If you can't or shouldn't bake explicit values, this is an environment/IT issue: the
COM-launched Aspen lacks VLE databank access under virtualization. Hand IT the evidence
bundle (`live_aspen_summary.json`, generated `.his`, `context_probe.json`, stdout/stderr,
Event Viewer excerpts, OS/.NET version, the exact missing-assembly message, Fusion/.NET
logs). Ask for AppsAnywhere **"Pre-fetch all"** and **package repair** for the missing
Aspen localization assemblies.

## Impact calibration — don't over-react to the warning

For the bundled methanol case the warning is **low-impact**: Gate-1 batch (real databank
NRTL) gives MEOH-PRO ≈ 99.92 mol% methanol, essentially equal to the zeroed-NRTL COM
result (≈ 99.89%). Methanol–water is only mildly non-ideal (no azeotrope) and the product
is **CO2-limited, not water-limited**, so zeroed methanol–water NRTL barely changes purity.

Confirm impact before spending effort on a fix: compare the Gate-1 batch result (real
databank thermo) against the Gate-2 COM result for your KPI of interest. If they agree,
the warning is cosmetic for that model and an explicit-parameter fix is about clearing the
warning, not about correcting a physics error.
