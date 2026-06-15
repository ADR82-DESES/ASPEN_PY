# Vent-Recovery Flash Tuning (Rate-Limited Reactor Loss Recovery)

A reusable pattern for closing acceptance when the reactor is **rate-limited** and the
remaining gap is product **lost to the vent**, not product not formed.

## When this applies

Diagnose first (see `systematic-debugging`). This pattern fits when:

- The reactor (e.g. `B-SYN` RPLUG) is **rate-limited** — methanol formation is fixed
  (~14454 kmol/hr for the bundled case) and does **not** rise with more feed or geometry.
  → You cannot make more product; you can only **recover** what's being lost.
- Production just-misses the floor and component loss at the vent is just-over the cap.
  For the bundled case after the NRTL fix: production 9712 (< 9800) and vent CH3OH loss
  686 (> 629).

## What does NOT work (verified dead ends)

- **Colder lights-flash.** The lights flash (`B-LCOOL`/`B-LFLA`) is already near-optimal at
  **50 °C**. Going colder (20 °C → 858 TPD vent) or hotter (70 °C → 1765 TPD vent) is
  worse. Colder re-dissolves CO2 into `REC-MEOH`, which then re-vents at the inefficient
  degasser `B-PDEG`. Don't chase vent loss at the lights flash.
- **Raising reactor geometry / feed** to make more product — the reactor is rate-limited,
  so this just changes the loop, not the methanol made.

## What works: a dedicated vent-recovery flash

Add a `FLASH2` on the **combined vent** to knock back condensable methanol and recycle it:

```
MIX-VENT → VNT-RAW → B-VFLA(FLASH2) → { VENT-TOT (final dry gas),
                                        VNT-REC → MIX-COL (recycle) }
```

`B-VFLA` settings for the bundled methanol case: **TEMP = 40 °C, PRES = 1.5 bar**.

### Temperature is a sweet spot, not "colder is better"

| B-VFLA temp | outcome                                                        |
| ----------- | ------------------------------------------------------------- |
| 25 °C       | **over-recovers** → production 10287 TPD > +2% ceiling (fail) |
| **40 °C**   | production **10114**, vent **292 TPD**, purity **99.89%** — all checks pass |
| 70 °C       | under-recovers → vent loss too high                           |

Too cold over-recovers and busts the upper production ceiling; too warm leaves product in
the vent. 40 °C is the sweet spot for this case. Re-scan for any other process.

## Result (acceptance closed)

With correct NRTL + `B-VFLA` at 40 °C:

- `warnings = []`, `run_status = converged`
- production **10113.7 TPD**, methanol **10102.5 TPD**, purity **99.889%**
- `VENT-TOT` CH3OH loss **291.9 TPD** (well under cap)
- **all acceptance checks pass**

## YAML wiring summary

- New block `B-VFLA` (`FLASH2`, `TEMP: 40.0`, `PRES: 1.5`).
- Flowsheet: `MIX-VENT → VNT-RAW`; `B-VFLA`: `VNT-RAW → {VENT-TOT, VNT-REC}`;
  add `VNT-REC` to the `MIX-COL` inputs.
- Streams: add `VNT-RAW`, `VNT-REC`; redefine `VENT-TOT` as the dry-gas product.

> Editing `process.yaml` from Python can rewrite line endings (CRLF vs the file's LF),
> producing a giant spurious diff. Normalize back to **LF** after a programmatic edit so
> the real change stays reviewable.
