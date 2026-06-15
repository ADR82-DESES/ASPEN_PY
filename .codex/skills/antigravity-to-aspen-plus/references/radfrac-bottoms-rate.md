# RADFRAC `bottoms_rate` Is Absolute — Track the Heavy-Key Load

A `RADFRAC` `bottoms_rate` is an **absolute mass (or mole) rate**, not an intensive spec.
It forces exactly that much material out the bottoms regardless of the column feed, so it
must equal the **real heavy-key (+ heavies) load** in that feed — and be **re-tracked** at
every feed/scale change.

## The defect (both directions)

| `bottoms_rate` vs real heavy-key load | failure                                                |
| ------------------------------------- | ------------------------------------------------------ |
| **too high**                          | drags the **light key** (methanol) down into the bottoms → yield lost to `WASTE-H2O` |
| **too low**                           | the heavy key (water) can't all leave the bottoms → **breaks overhead** into the distillate → purity loss |

Concrete cost of "too high": a `bottoms_rate` of 82000 against a real column-feed water
load of ~16.5k kg/hr forced **~1571 TPD of methanol** out the bottoms (silent yield loss
even though the column "converged").

## How to set it

1. From a converged run, read the **column feed** stream (e.g. `CRUDE-LQ`) in
   `streams.csv` and sum the **water + heavies** mass rate. That is your target
   `bottoms_rate`.
2. Add a small **cushion** (~10%) biased toward whichever failure is costlier. For
   AA-grade methanol, a slight excess protects purity (water cannot break overhead) at the
   cost of a little methanol slip — quantify it: a +10% cushion cost ~27.6 TPD (0.28%)
   methanol-to-bottoms vs ~100 kg/hr of purity headroom.

## Re-track at every scale

Because it is absolute, `bottoms_rate` does **not** ride along with a self-similar feed
scale (`references/self-similar-plant-scaling.md`). Recompute it from the new column-feed
water load each time the feeds change; a stale value reproduces the defect at the new
scale.

## Diagnostic signals

- High `CH3OH` in the **bottoms** (`WASTE-H2O`) → `bottoms_rate` too high.
- High `H2O` in the **product / distillate** (`MEOH-PRO`) → `bottoms_rate` too low.

## Verified example (downscaled 10k methanol)

Column-feed water ~11050 kg/hr → `bottoms_rate: 12200` (water + ~10%). Result: bottoms
**90.6% water**, product water **7e-6** mass frac, purity **99.88%**.
