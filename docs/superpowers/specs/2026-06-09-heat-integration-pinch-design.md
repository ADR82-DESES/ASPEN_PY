# Heat-Integration Pinch Analysis (post-processing) — Design

**Date:** 2026-06-09
**Status:** Approved (design)
**Part of:** Process-fidelity upgrade. This is a new sub-project, independent of the kinetics
work (2a/2b) and of items #1/#3/#4. It addresses the energy-fidelity gap surfaced when the
methanol run reported `energy_consumption_mw = 2755.6` — which is literally
`duty_mw.abs().sum()` (`extractor.py:1210`), a sum of *absolute* block duties with no netting,
no heat recovery, and no shaft work.

## Problem

The methanol deck is **not heat-integrated**: every heating/cooling task is a standalone
`HEATER`/reactor/column duty against utilities (no `HEATX` blocks exist in the generator;
`VALID_BLOCK_TYPES` has only `HEATER`). The single largest term, `B-COOL = −1078 MW`
(reformer-effluent cooling), is heat a real plant recovers as HP steam. So the energy KPI is
not representative of an integrated plant, and it omits compressor shaft work entirely.

## Goal

A pure-Python post-processing module that runs on a converged run's `results/` artifacts and
reports the **thermodynamic heat-integration target** via pinch analysis: minimum hot/cold
utility, maximum recovery, steam-level and power balance, and a redefined energy KPI. No Aspen
calls, no flowsheet changes, no re-simulation.

## Decisions (user-approved)

- **Pinch energy-targeting**, post-processing only (not an in-deck HEATX network).
- **Endpoint-linear thermal streams** (CP = |duty|/ΔT between inlet/outlet T) with isothermal
  flags for phase-change duties (condenser/reboiler/clearly-latent loads). No new Aspen
  extraction.
- **Include steam-level targeting (HP/MP/LP) + turbine-drive power balance** in v1.
- **Redefine `energy_consumption_mw`** to the representative integrated value, and add a
  structured `energy.*` block (the gross Σ|duty| number is preserved inside it, clearly
  labelled, so the information is not lost).
- **Compressor shaft work** is read straight from `blocks.csv` (the `n_kw`/work column).
- **Develop/validate against fresh LHHW artifacts**: the user re-runs the methanol notebook on
  the now-merged LHHW deck first; the module is built and sanity-checked against those artifacts
  (the June-5 artifacts are pre-LHHW and only used as a structural fixture if needed).

## Architecture — `aspen_automation/heat_integration/`

Each unit is small, pure, and independently testable.

### `thermal_streams.py` — converged artifacts → thermal streams
Input: `streams.csv` (stream temperatures), `energy_balance.csv` / `blocks.csv` (per-block
duties incl. separate `condenser_n`/`reboiler_n`), and the flowsheet block→stream map (from the
spec). Output: a list of `ThermalStream(name, t_supply_c, t_target_c, duty_mw, kind, isothermal)`
where `kind ∈ {hot, cold}`:
- `HEATER`/`FLASH2` with non-trivial duty → inlet-stream T → outlet-stream T.
- Reactor duties (`B-ATR`, `B-SYN`) → near-isothermal stream at the reactor temperature.
- `RADFRAC` → two isothermal streams: condenser (hot, at distillate T) and reboiler (cold, at
  bottoms T), from the separately captured duties.
- Sign convention: `duty<0` → **hot** stream (gives up heat, needs cooling); `duty>0` → **cold**
  stream (needs heating). Near-zero duties (|duty| < tolerance) are dropped.
- Phase-change/latent duties set `isothermal=True` (supply≈target at saturation T) — the
  reformer-effluent condensation caveat.

### `pinch.py` — Problem Table Algorithm
Pure function `pinch_analysis(streams, dt_min) -> PinchResult`:
- Shift temperatures by ΔTmin/2, form temperature intervals, cascade interval heat balances.
- Returns: `pinch_temperature_c`, `min_hot_utility_mw`, `min_cold_utility_mw`,
  `max_recovery_mw`, plus the **hot/cold composite curves** and the **grand composite curve**
  (lists of (T, cumulative-H) points).
- Validated against a published textbook 4-stream problem (unambiguous Q_Hmin/Q_Cmin/pinch).

### `utility_targeting.py` — steam levels + power balance
`target_utilities(pinch_result, steam_levels, compressor_work_mw, turbine_efficiency)`:
- Place each steam level's saturation temperature against the grand composite curve → heat that
  can **raise** steam (above pinch) and heat **demanded** at each level (below pinch).
- Expand raised HP steam through a turbine at `turbine_efficiency` → shaft power; net against
  `compressor_work_mw` → `net_power_mw` (signed; + = import, − = export).
- Returns `steam_raised_by_level`, `turbine_power_mw`, `compressor_work_mw`, `net_power_mw`.

### `energy_kpi.py` — redefined KPI
`build_energy_kpi(thermal_streams, pinch_result, utility_target) -> dict`:
```
energy:
  gross_heating_mw, gross_cooling_mw, net_duty_mw          # the un-integrated reality
  gross_abs_duty_mw                                         # the old Σ|duty| value, preserved/labelled
  integrated:
    dt_min_c, pinch_temperature_c,
    min_hot_utility_mw, min_cold_utility_mw, max_recovery_mw
  steam_power:
    steam_raised_by_level, turbine_power_mw, compressor_work_mw, net_power_mw
energy_consumption_mw: <representative>      # REDEFINED headline
```
**`energy_consumption_mw` (redefined)** = `min_hot_utility_mw + net_power_mw` — the representative
imported energy of the integrated plant (fired/utility heat after recovery, plus net imported
shaft power; a steam export shows as a credit via negative `net_power_mw`). The simplification of
adding heat-MW and power-MW into one figure is acknowledged; the structured block keeps them
separate. A unit test pins this formula.

### `heat_integration_figures.py` — plots
Nature-style **hot/cold composite curves** and **grand composite curve** (with steam levels
drawn as horizontal lines), reusing `figure_style.use_nature_style()`. Slots into the existing
dashboard alongside the mass/energy Sankeys.

## Data flow

converged `results/` (`streams.csv`, `energy_balance.csv`/`blocks.csv`) + spec flowsheet →
`thermal_streams` → `pinch.pinch_analysis` (targets + curves) → `utility_targeting`
(steam + power) → `energy_kpi.build_energy_kpi` (redefined KPI) + `heat_integration_figures`
(composite/GCC plots in the dashboard). Wired into the extractor's KPI build and the dashboard;
also callable standalone on any run directory.

## Config

Optional `heat_integration` block in `process.yaml` (else module defaults):
- `dt_min`: 10 °C (default)
- `steam_levels`: HP ≈ 100 bar / 540 °C, MP ≈ 40 bar (sat), LP ≈ 6 bar (sat) (defaults)
- `turbine_efficiency`: 0.80 (default)

## Error handling

- Missing/empty artifacts → return a clearly-flagged "heat integration unavailable" KPI block
  (no crash), mirroring how the dashboard already degrades.
- A stream with ΔT→0 but non-zero duty is treated as isothermal (avoids divide-by-zero CP).
- If no hot or no cold streams exist, targets degrade gracefully (Q_Hmin = total heating, etc.).

## Testing

- **Pinch engine golden test:** a published 4-stream pinch problem with known
  Q_Hmin/Q_Cmin/pinch temperature is the primary acceptance test.
- **Thermal-stream extraction:** unit tests from a synthetic `streams.csv` + duties +
  flowsheet, asserting hot/cold classification, endpoints, and isothermal flags.
- **Steam/power targeting:** unit tests against a known grand composite curve and a known
  compressor work / turbine efficiency.
- **KPI builder:** asserts the structured shape and the `energy_consumption_mw` formula.
- **Integration sanity:** run the full chain on a real run's `results/` and assert
  `min_hot_utility ≤ gross_heating`, `max_recovery ≥ 0`, and energy-balance closure.

## Validation boundary

The module reports the **thermodynamic recovery target** an integrated plant could achieve at
the chosen ΔTmin — not a re-simulated heat-exchanger network. It honestly replaces the
misleading Σ|duty| headline with Q_Hmin + net power and quantifies the recovery the current deck
leaves on the table. Building the actual in-deck HEATX network (waste-heat boiler, feed-effluent
exchangers, steam turbine) remains a separate, larger sub-project for later if desired.

## Out of scope

- In-deck `HEATX`/`MHEATX` generator support and flowsheet re-plumbing.
- Detailed exchanger sizing (areas, ΔP, fouling) and a full utility-system simulation.
- Items #1 (EOS), #3 (SN), #4 (two-column distillation).

## Decomposition (task order for the plan)

1. `thermal_streams.py` + tests.
2. `pinch.py` + golden textbook test.
3. `utility_targeting.py` + tests.
4. `energy_kpi.py` (redefine `energy_consumption_mw`, update extractor) + tests.
5. `heat_integration_figures.py` + dashboard wiring.
6. Integration sanity test on a real LHHW run's artifacts.
