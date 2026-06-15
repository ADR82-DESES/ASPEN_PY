# Recovering Binary Interaction Parameters by Activity-Coefficient Calibration

When the COM engine zeroes a databank parameter
(see [com-under-appsanywhere.md](com-under-appsanywhere.md)) and the stored value is
DRM-encrypted (see [aspen-databank-sql.md](aspen-databank-sql.md)), you can still recover
the **real** coefficients without touching the encryption: let Aspen's **batch engine**
(which *does* have the decrypted parameters) compute activity coefficients γ on a grid,
then least-squares fit the model to those γ. This is fully sanctioned — you only read
Aspen's own published outputs.

## Recipe

1. **Build a probe flowsheet** for the binary pair: a single `FLASH2` (or even a stream
   report) over a grid of temperature `T` and liquid mole fraction `x`.

2. **Emit γ to the report.** Add a property set and request it on the stream report:

   ```
   PROP-SET PS GAMMA SUBSTREAM=MIXED PHASE=L
   ...
   STREAM-REPOR ... PROPERTIES=PS
   ```

   (`PROP-SET PS GAMMA SUBSTREAM=MIXED PHASE=L` then `PROPERTIES=PS` on `STREAM-REPOR`.)

3. **Run via the batch engine** (Gate 1 path) — it retrieves the real databank NRTL — and
   **read GAMMA from the `.rep`** for each grid point.

4. **Least-squares fit** the model parameters to `ln γ` over the grid.
   For NRTL with `cij = α`, do an **α-scan**: fix α at a series of values, fit the rest,
   and take the α with the minimum residual. The minimum is sharp.

## Result for methanol(1)–water(2), VLE-IG

Recovered with an α-scan minimum sharp at **0.30** and RMS in `ln γ` of **2e-5**
(component order CH3OH → H2O):

| param      | value      |
| ---------- | ---------- |
| `aij`      | -0.69201   |
| `aji`      | 2.73113    |
| `bij` (K)  | 172.6353   |
| `bji` (K)  | -616.882   |
| `cij` (α)  | 0.30       |

These are baked into `process_library/methanol/process.yaml` as a `source_type: explicit`
binary parameter, so they survive the COM load. Verified γ at the check state:
**1.1323 / 1.1909**.

## Pitfalls / gotchas

- `load_spec(...)` returns a **dict**, not an object — index it as a dict in scratch probes.
- `IN-UNITS FLOW='KMOL/HR'` is rejected by the batch translator in this context — use
  `KG/HR`.
- `DIAGNOSTICS PROP-LEVEL=8` / `HISTORY=8` are rejected — don't rely on them to dump γ;
  use `PROP-SET` + `STREAM-REPOR` instead.
- Read the *batch* `.rep`, not the COM result — the whole point is that only the batch
  engine has the decrypted parameters.

## Generalizing to other pairs/models

The method is model-agnostic: anything Aspen can report (γ, fugacity, K-values, excess
enthalpy) over a (T, x) grid can be fit back to the model's parameters. Match the
property to the parameters you're recovering, keep the grid inside the model's valid range,
and scan any shape parameter (like NRTL α) rather than fitting it jointly.
