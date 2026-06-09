# Heat-Integration Pinch Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pure-Python post-processing package that runs pinch analysis on a converged run's artifacts and replaces the misleading `energy_consumption_mw = Σ|duty|` KPI with a representative integrated value (Q_Hmin + net shaft power), plus steam/power targeting and composite/grand-composite figures.

**Architecture:** New package `aspen_automation/heat_integration/` with small, pure, independently-testable units: `config` → `thermal_streams` (artifacts → hot/cold streams) → `pinch` (Problem Table Algorithm → targets + curves) → `utility_targeting` (steam raising + turbine power) → `energy_kpi` (redefined KPI dict). An `analyze_heat_integration(...)` orchestrator wires them; the extractor calls it. `heat_integration_figures` plots the curves; the dashboard saves them. No Aspen calls, no flowsheet changes, no re-simulation.

**Tech Stack:** Python 3, pandas, numpy, matplotlib (via existing `figure_style`), dataclasses; pytest.

**Spec:** `docs/superpowers/specs/2026-06-09-heat-integration-pinch-design.md`

---

## Conventions (read first)

- **Worktree:** all work happens in `.worktrees/heat-integration` on branch `feature/heat-integration-pinch`.
- **Test command (this machine):** always pass `--basetemp=.pytest_tmp` — a stale ACL on `%TEMP%\pytest-of-domingueza` breaks the default `tmp_path` fixture. Example:
  `pixi run python -m pytest tests/unit/test_pinch.py --basetemp=.pytest_tmp -q`
- **Baseline (pre-existing, do NOT try to fix — unrelated files):** 3 failing tests exist on the branch: `test_inp_generator.py::test_generate_inp_emits_canonical_methanol_lights_recovery_section` and 2× `test_kinetic_diagnostics.py::test_reactor_only_sweep_*`. This work touches none of those files.
- **Fixture data:** `tests/fixtures/lhhw_run/{blocks.csv,streams.csv,energy_balance.csv,kpis.json}` is a committed copy of the converged LHHW methanol run (`run_2026-06-09_12-03-06`). Used by Task 7.
- **Sign convention everywhere:** a stream/block `duty_mw < 0` is **hot** (gives up heat, needs cooling); `duty_mw > 0` is **cold** (needs heating). This matches `blocks.csv`.
- **Commits:** scope `git add` to the files in each task. End commit messages with the `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` trailer.

## File Structure

| File | Responsibility |
|------|----------------|
| `aspen_automation/heat_integration/__init__.py` | Package exports + `analyze_heat_integration(...)` orchestrator + `figures_for_run(...)` + `_compressor_work_mw(...)` |
| `aspen_automation/heat_integration/config.py` | `SteamLevel`, `HeatIntegrationConfig` (defaults + `from_spec`) |
| `aspen_automation/heat_integration/thermal_streams.py` | `ThermalStream` + `extract_thermal_streams(blocks_df, streams_df, flowsheet)` |
| `aspen_automation/heat_integration/pinch.py` | `PinchResult` + `pinch_analysis(streams, dt_min)` + `build_composite_curves(streams)` |
| `aspen_automation/heat_integration/utility_targeting.py` | `UtilityTarget` + `target_utilities(...)` |
| `aspen_automation/heat_integration/energy_kpi.py` | `build_energy_kpi(...)` |
| `aspen_automation/heat_integration/heat_integration_figures.py` | `fig_composite_curves(...)`, `fig_grand_composite(...)` |
| `aspen_automation/extractor.py` (modify ~1209) | call orchestrator; redefine `energy_consumption_mw`; add `energy` block |
| `aspen_automation/dashboard.py` (modify `save_dashboard_figures`) | save the two heat-integration figures (guarded) |

Test files (all under `tests/`): `unit/test_heat_integration_config.py`, `unit/test_thermal_streams.py`, `unit/test_pinch.py`, `unit/test_utility_targeting.py`, `unit/test_energy_kpi.py`, `unit/test_heat_integration_figures.py`, `integration/test_heat_integration_pipeline.py`.

---

## Task 1: Config (`SteamLevel`, `HeatIntegrationConfig`)

**Files:**
- Create: `aspen_automation/heat_integration/__init__.py` (empty for now)
- Create: `aspen_automation/heat_integration/config.py`
- Test: `tests/unit/test_heat_integration_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_heat_integration_config.py
from aspen_automation.heat_integration.config import HeatIntegrationConfig, SteamLevel


def test_defaults_when_no_heat_integration_block():
    cfg = HeatIntegrationConfig.from_spec({"flowsheet": []})
    assert cfg.dt_min_c == 10.0
    assert cfg.turbine_efficiency == 0.80
    assert cfg.condenser_temp_c == 40.0
    assert [lv.name for lv in cfg.steam_levels] == ["HP", "MP", "LP"]
    assert cfg.steam_levels[0].t_sat_c == 311.0


def test_overrides_from_spec_block():
    spec = {
        "heat_integration": {
            "dt_min": 15,
            "turbine_efficiency": 0.7,
            "condenser_temp_c": 35,
            "steam_levels": [
                {"name": "VHP", "t_sat_c": 330, "pressure_bar": 120},
                {"name": "LP", "t_sat_c": 150},
            ],
        }
    }
    cfg = HeatIntegrationConfig.from_spec(spec)
    assert cfg.dt_min_c == 15.0
    assert cfg.turbine_efficiency == 0.7
    assert cfg.condenser_temp_c == 35.0
    assert [lv.name for lv in cfg.steam_levels] == ["VHP", "LP"]
    assert cfg.steam_levels[1].pressure_bar == 0.0  # missing pressure → 0.0


def test_from_spec_handles_none_and_non_dict():
    assert HeatIntegrationConfig.from_spec(None).dt_min_c == 10.0
    assert HeatIntegrationConfig.from_spec({"heat_integration": "nope"}).dt_min_c == 10.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pixi run python -m pytest tests/unit/test_heat_integration_config.py --basetemp=.pytest_tmp -q`
Expected: FAIL (ModuleNotFoundError: aspen_automation.heat_integration.config)

- [ ] **Step 3: Create the empty package init and the config module**

Create `aspen_automation/heat_integration/__init__.py` as an empty file (one blank line is fine).

Create `aspen_automation/heat_integration/config.py`:

```python
"""Configuration for heat-integration pinch analysis.

Defaults model a typical methanol/ATR utility system. Override via an optional
``heat_integration`` block in process.yaml.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class SteamLevel:
    """A steam header: name, saturation temperature (°C), header pressure (bar)."""

    name: str
    t_sat_c: float
    pressure_bar: float


# Saturation temperatures: 100 bar ≈ 311 °C, 40 bar ≈ 250 °C, 6 bar ≈ 159 °C.
DEFAULT_STEAM_LEVELS: List[SteamLevel] = [
    SteamLevel("HP", 311.0, 100.0),
    SteamLevel("MP", 250.0, 40.0),
    SteamLevel("LP", 159.0, 6.0),
]


@dataclass(frozen=True)
class HeatIntegrationConfig:
    dt_min_c: float = 10.0
    steam_levels: List[SteamLevel] = field(
        default_factory=lambda: list(DEFAULT_STEAM_LEVELS)
    )
    turbine_efficiency: float = 0.80
    condenser_temp_c: float = 40.0

    @classmethod
    def from_spec(cls, spec: Optional[Dict[str, Any]]) -> "HeatIntegrationConfig":
        block = spec.get("heat_integration") if isinstance(spec, dict) else None
        if not isinstance(block, dict):
            return cls()
        dt_min = float(block.get("dt_min", block.get("dt_min_c", 10.0)))
        eff = float(block.get("turbine_efficiency", 0.80))
        cond = float(block.get("condenser_temp_c", 40.0))
        levels_raw = block.get("steam_levels")
        if isinstance(levels_raw, list) and levels_raw:
            levels = [
                SteamLevel(
                    str(lv.get("name", f"L{i}")),
                    float(lv["t_sat_c"]),
                    float(lv.get("pressure_bar", 0.0)),
                )
                for i, lv in enumerate(levels_raw)
                if isinstance(lv, dict) and "t_sat_c" in lv
            ]
        else:
            levels = list(DEFAULT_STEAM_LEVELS)
        return cls(
            dt_min_c=dt_min,
            steam_levels=levels,
            turbine_efficiency=eff,
            condenser_temp_c=cond,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pixi run python -m pytest tests/unit/test_heat_integration_config.py --basetemp=.pytest_tmp -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add aspen_automation/heat_integration/__init__.py aspen_automation/heat_integration/config.py tests/unit/test_heat_integration_config.py
git commit -m "feat(heat-integration): config with steam levels and defaults"
```

---

## Task 2: Thermal-stream extraction

**Files:**
- Create: `aspen_automation/heat_integration/thermal_streams.py`
- Test: `tests/unit/test_thermal_streams.py`

Classification rules:
- **Reactors** (`RGIBBS`, `RPLUG`, `REQUIL`): isothermal stream at the outlet-stream temperature.
- **HEATER/FLASH2**: sloping stream from inlet-stream T to outlet-stream T (or isothermal if `|ΔT| < 1 °C`).
- **RADFRAC**: two isothermal streams — condenser (hot, at distillate = first output T) and reboiler (cold, at bottoms = second output T) — from `condenser_duty_mw` / `reboiler_duty_mw`.
- Drop `|duty| < 0.5 MW` (numerical noise / no-duty units) and all other block types (`MIXER`, `COMPR`, `VALVE`, `FSPLIT`, `SEP`).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_thermal_streams.py
import pandas as pd

from aspen_automation.heat_integration.thermal_streams import (
    ThermalStream,
    extract_thermal_streams,
)

FLOWSHEET = [
    {"block": "B-COOL", "inputs": ["HOT"], "outputs": ["COLD"]},
    {"block": "B-RX", "inputs": ["RIN"], "outputs": ["ROUT"]},
    {"block": "B-COL", "inputs": ["FEED"], "outputs": ["DIST", "BOTS"]},
    {"block": "B-NIL", "inputs": ["X"], "outputs": ["Y"]},
    {"block": "B-MIX", "inputs": ["A", "B"], "outputs": ["C"]},
]

STREAMS = pd.DataFrame(
    {
        "stream_name": ["HOT", "COLD", "RIN", "ROUT", "FEED", "DIST", "BOTS", "X", "Y", "A", "B", "C"],
        "temperature": [1000.0, 40.0, 100.0, 250.0, 50.0, 37.0, 89.0, 60.0, 60.4, 30.0, 30.0, 30.0],
    }
)

BLOCKS = pd.DataFrame(
    {
        "block_name": ["B-COOL", "B-RX", "B-COL", "B-NIL", "B-MIX"],
        "block_type": ["HEATER", "RPLUG", "RADFRAC", "FLASH2", "MIXER"],
        "duty_mw": [-1077.0, -365.0, None, 0.1, None],
        "condenser_duty_mw": [None, None, -615.0, None, None],
        "reboiler_duty_mw": [None, None, 613.0, None, None],
    }
)


def _by_name(streams):
    return {s.name: s for s in streams}


def test_heater_is_sloping_hot_stream():
    s = _by_name(extract_thermal_streams(BLOCKS, STREAMS, FLOWSHEET))["B-COOL"]
    assert s == ThermalStream("B-COOL", 1000.0, 40.0, -1077.0, "hot", False)
    assert s.cp_mw_per_c == 1077.0 / 960.0


def test_reactor_is_isothermal_at_outlet_temperature():
    s = _by_name(extract_thermal_streams(BLOCKS, STREAMS, FLOWSHEET))["B-RX"]
    assert s == ThermalStream("B-RX", 250.0, 250.0, -365.0, "hot", True)


def test_radfrac_splits_into_condenser_and_reboiler():
    out = _by_name(extract_thermal_streams(BLOCKS, STREAMS, FLOWSHEET))
    assert out["B-COL-COND"] == ThermalStream("B-COL-COND", 37.0, 37.0, -615.0, "hot", True)
    assert out["B-COL-REB"] == ThermalStream("B-COL-REB", 89.0, 89.0, 613.0, "cold", True)


def test_near_zero_duty_and_non_thermal_blocks_dropped():
    names = {s.name for s in extract_thermal_streams(BLOCKS, STREAMS, FLOWSHEET)}
    assert "B-NIL" not in names  # |0.1| < 0.5 MW
    assert "B-MIX" not in names  # MIXER carries no thermal duty


def test_flash2_with_tiny_temperature_span_is_isothermal():
    blocks = pd.DataFrame(
        {
            "block_name": ["B-FL"],
            "block_type": ["FLASH2"],
            "duty_mw": [120.0],
            "condenser_duty_mw": [None],
            "reboiler_duty_mw": [None],
        }
    )
    streams = pd.DataFrame({"stream_name": ["IN", "OUT"], "temperature": [80.0, 80.3]})
    fs = [{"block": "B-FL", "inputs": ["IN"], "outputs": ["OUT"]}]
    s = extract_thermal_streams(blocks, streams, fs)[0]
    assert s == ThermalStream("B-FL", 80.3, 80.3, 120.0, "cold", True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pixi run python -m pytest tests/unit/test_thermal_streams.py --basetemp=.pytest_tmp -q`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement `thermal_streams.py`**

```python
"""Convert converged run artifacts into hot/cold thermal streams for pinch analysis."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd

NEAR_ZERO_DUTY_MW = 0.5   # |duty| below this is dropped (noise / no-duty units)
ISOTHERMAL_DT_C = 1.0     # |Tin - Tout| below this is treated as isothermal

REACTOR_TYPES = {"RGIBBS", "RPLUG", "REQUIL"}
SLOPING_TYPES = {"HEATER", "FLASH2"}


@dataclass(frozen=True)
class ThermalStream:
    name: str
    t_supply_c: float
    t_target_c: float
    duty_mw: float          # signed: <0 hot (needs cooling), >0 cold (needs heating)
    kind: str               # "hot" | "cold"
    isothermal: bool

    @property
    def cp_mw_per_c(self) -> float:
        span = abs(self.t_supply_c - self.t_target_c)
        return 0.0 if span == 0 else abs(self.duty_mw) / span


def _num(value: Any) -> Optional[float]:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def _kind(duty_mw: float) -> str:
    return "hot" if duty_mw < 0 else "cold"


def _temps_by_stream(streams_df: pd.DataFrame) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for _, row in streams_df.iterrows():
        name = row.get("stream_name")
        temp = _num(row.get("temperature"))
        if isinstance(name, str) and temp is not None:
            out[name] = temp
    return out


def _io_by_block(flowsheet: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[str]]]:
    out: Dict[str, Dict[str, List[str]]] = {}
    for conn in flowsheet or []:
        block = conn.get("block")
        if isinstance(block, str):
            out[block] = {
                "inputs": list(conn.get("inputs") or []),
                "outputs": list(conn.get("outputs") or []),
            }
    return out


def extract_thermal_streams(
    blocks_df: pd.DataFrame,
    streams_df: pd.DataFrame,
    flowsheet: List[Dict[str, Any]],
) -> List[ThermalStream]:
    temps = _temps_by_stream(streams_df)
    io = _io_by_block(flowsheet)
    streams: List[ThermalStream] = []

    for _, row in blocks_df.iterrows():
        name = row.get("block_name")
        btype = row.get("block_type")
        if not isinstance(name, str) or not isinstance(btype, str):
            continue
        conn = io.get(name, {"inputs": [], "outputs": []})
        inputs, outputs = conn["inputs"], conn["outputs"]

        if btype == "RADFRAC":
            cond = _num(row.get("condenser_duty_mw"))
            reb = _num(row.get("reboiler_duty_mw"))
            dist_t = temps.get(outputs[0]) if len(outputs) >= 1 else None
            bot_t = temps.get(outputs[1]) if len(outputs) >= 2 else None
            if cond is not None and abs(cond) >= NEAR_ZERO_DUTY_MW and dist_t is not None:
                streams.append(
                    ThermalStream(f"{name}-COND", dist_t, dist_t, cond, _kind(cond), True)
                )
            if reb is not None and abs(reb) >= NEAR_ZERO_DUTY_MW and bot_t is not None:
                streams.append(
                    ThermalStream(f"{name}-REB", bot_t, bot_t, reb, _kind(reb), True)
                )
            continue

        duty = _num(row.get("duty_mw"))
        if duty is None or abs(duty) < NEAR_ZERO_DUTY_MW:
            continue

        if btype in REACTOR_TYPES:
            t_out = temps.get(outputs[0]) if outputs else None
            if t_out is None:
                continue
            streams.append(ThermalStream(name, t_out, t_out, duty, _kind(duty), True))
        elif btype in SLOPING_TYPES:
            t_in = temps.get(inputs[0]) if inputs else None
            t_out = temps.get(outputs[0]) if outputs else None
            if t_in is None or t_out is None:
                continue
            if abs(t_in - t_out) < ISOTHERMAL_DT_C:
                streams.append(ThermalStream(name, t_out, t_out, duty, _kind(duty), True))
            else:
                streams.append(ThermalStream(name, t_in, t_out, duty, _kind(duty), False))
        # other block types carry no thermal duty → skipped
    return streams
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pixi run python -m pytest tests/unit/test_thermal_streams.py --basetemp=.pytest_tmp -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add aspen_automation/heat_integration/thermal_streams.py tests/unit/test_thermal_streams.py
git commit -m "feat(heat-integration): extract hot/cold thermal streams from run artifacts"
```

---

## Task 3: Pinch engine (Problem Table Algorithm + curves)

**Files:**
- Create: `aspen_automation/heat_integration/pinch.py`
- Test: `tests/unit/test_pinch.py`

The golden test is a four-stream problem with a **fully hand-derived Problem Table** (shown below). With ΔTmin = 10 °C:

| Stream | Kind | Ts (°C) | Tt (°C) | CP (MW/°C) | ΔH |
|--------|------|---------|---------|------------|------|
| H1 | hot | 200 | 40 | 3.0 | −480 |
| H2 | hot | 150 | 40 | 1.0 | −110 |
| C1 | cold | 30 | 180 | 2.0 | +300 |
| C2 | cold | 50 | 160 | 4.0 | +440 |

Shift hot −5, cold +5 → boundaries (desc): 195, 185, 165, 145, 55, 35. Interval surpluses `(ΣCP_hot−ΣCP_cold)·ΔT`: +30, +20, −60, −180, +40. Infeasible cascade from 0: 0, 30, 50, −10, −190, −150 → min −190 ⇒ **Q_Hmin = 190**. Feasible (add 190): 190, 220, 240, 180, 0, 40 ⇒ **Q_Cmin = 40**, **pinch (shifted) = 55 °C**. Energy balance check: total hot 590, total cold 740, net 150 = 190 − 40 ✓. **Max recovery = 590 − 40 = 550**. Grand composite (feasible cascade) = `[(195,190),(185,220),(165,240),(145,180),(55,0),(35,40)]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_pinch.py
import pytest

from aspen_automation.heat_integration.pinch import pinch_analysis, build_composite_curves
from aspen_automation.heat_integration.thermal_streams import ThermalStream

GOLDEN = [
    ThermalStream("H1", 200.0, 40.0, -480.0, "hot", False),   # CP 3.0
    ThermalStream("H2", 150.0, 40.0, -110.0, "hot", False),   # CP 1.0
    ThermalStream("C1", 30.0, 180.0, 300.0, "cold", False),   # CP 2.0
    ThermalStream("C2", 50.0, 160.0, 440.0, "cold", False),   # CP 4.0
]


def test_four_stream_targets():
    r = pinch_analysis(GOLDEN, dt_min=10.0)
    assert r.min_hot_utility_mw == pytest.approx(190.0)
    assert r.min_cold_utility_mw == pytest.approx(40.0)
    assert r.pinch_temperature_c == pytest.approx(55.0)
    assert r.max_recovery_mw == pytest.approx(550.0)


def test_four_stream_grand_composite():
    r = pinch_analysis(GOLDEN, dt_min=10.0)
    expected = [(195.0, 190.0), (185.0, 220.0), (165.0, 240.0),
                (145.0, 180.0), (55.0, 0.0), (35.0, 40.0)]
    assert len(r.grand_composite) == len(expected)
    for (t, h), (et, eh) in zip(r.grand_composite, expected):
        assert t == pytest.approx(et)
        assert h == pytest.approx(eh)


def test_composite_curve_totals():
    hot, cold = build_composite_curves(GOLDEN)
    assert hot[0][1] == pytest.approx(0.0)
    assert hot[-1][1] == pytest.approx(590.0)    # total hot enthalpy
    assert cold[0][1] == pytest.approx(0.0)
    assert cold[-1][1] == pytest.approx(740.0)   # total cold enthalpy


def test_isothermal_latent_stream_goes_to_cold_utility():
    # H1/C1 balance exactly (both 120 MW over 100->40 / 30->90); an extra isothermal hot
    # latent load of 50 MW at 70 C has nothing to heat -> all 50 to cold utility.
    streams = [
        ThermalStream("H1", 100.0, 40.0, -120.0, "hot", False),
        ThermalStream("C1", 30.0, 90.0, 120.0, "cold", False),
        ThermalStream("HX", 70.0, 70.0, -50.0, "hot", True),
    ]
    r = pinch_analysis(streams, dt_min=10.0)
    assert r.min_hot_utility_mw == pytest.approx(0.0)
    assert r.min_cold_utility_mw == pytest.approx(50.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pixi run python -m pytest tests/unit/test_pinch.py --basetemp=.pytest_tmp -q`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement `pinch.py`**

```python
"""Problem Table Algorithm: pinch targets + composite / grand-composite curves.

Sensible streams contribute CP·ΔT across shifted-temperature intervals. Isothermal
(latent) streams contribute their whole duty as a point load at their shifted
temperature. Sign convention: a stream's contribution to interval *surplus* is
``-duty_mw`` (hot duty<0 -> +surplus; cold duty>0 -> -surplus).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from .thermal_streams import ThermalStream

Curve = List[Tuple[float, float]]


@dataclass(frozen=True)
class PinchResult:
    pinch_temperature_c: float          # shifted (mean) pinch temperature
    min_hot_utility_mw: float
    min_cold_utility_mw: float
    max_recovery_mw: float
    grand_composite: Curve              # (shifted_T, net heat flow H), descending T
    hot_composite: Curve                # (actual_T, cumulative H), ascending T
    cold_composite: Curve               # (actual_T, cumulative H), ascending T


def _shifted_endpoints(s: ThermalStream, shift: float) -> Tuple[float, float]:
    if s.kind == "hot":
        return s.t_supply_c - shift, s.t_target_c - shift
    return s.t_supply_c + shift, s.t_target_c + shift


def _one_composite(streams_of_kind: List[ThermalStream]) -> Curve:
    if not streams_of_kind:
        return []
    bounds = set()
    for s in streams_of_kind:
        bounds.add(round(min(s.t_supply_c, s.t_target_c), 6))
        bounds.add(round(max(s.t_supply_c, s.t_target_c), 6))
    temps = sorted(bounds)            # ascending (cold end first)
    curve: Curve = [(temps[0], 0.0)]
    h = 0.0
    for i in range(len(temps) - 1):
        t_lo, t_hi = temps[i], temps[i + 1]
        iso = sum(
            abs(s.duty_mw) for s in streams_of_kind
            if s.isothermal and round(s.t_supply_c, 6) == round(t_lo, 6)
        )
        if iso:
            h += iso
            curve.append((t_lo, h))   # vertical jump at the latent temperature
        cp = sum(
            s.cp_mw_per_c for s in streams_of_kind
            if not s.isothermal
            and min(s.t_supply_c, s.t_target_c) <= t_lo
            and max(s.t_supply_c, s.t_target_c) >= t_hi
        )
        h += cp * (t_hi - t_lo)
        curve.append((t_hi, h))
    top = temps[-1]
    iso_top = sum(
        abs(s.duty_mw) for s in streams_of_kind
        if s.isothermal and round(s.t_supply_c, 6) == round(top, 6)
    )
    if iso_top:
        h += iso_top
        curve.append((top, h))
    return curve


def build_composite_curves(streams: List[ThermalStream]) -> Tuple[Curve, Curve]:
    hot = _one_composite([s for s in streams if s.kind == "hot"])
    cold = _one_composite([s for s in streams if s.kind == "cold"])
    return hot, cold


def pinch_analysis(streams: List[ThermalStream], dt_min: float) -> PinchResult:
    shift = dt_min / 2.0
    sensible = [s for s in streams if not s.isothermal]
    isothermal = [s for s in streams if s.isothermal]

    bounds = set()
    for s in streams:
        a, b = _shifted_endpoints(s, shift)
        bounds.add(round(a, 6))
        bounds.add(round(b, 6))
    temps = sorted(bounds, reverse=True)

    hot_c, cold_c = build_composite_curves(streams)
    total_hot = sum(-s.duty_mw for s in streams if s.kind == "hot")

    if len(temps) < 2:
        surplus = sum(-s.duty_mw for s in streams)
        q_hmin = max(0.0, -surplus)
        q_cmin = max(0.0, surplus)
        pt = temps[0] if temps else 0.0
        return PinchResult(pt, q_hmin, q_cmin, max(0.0, total_hot - q_cmin),
                           [(pt, q_hmin)], hot_c, cold_c)

    iso_load = {t: 0.0 for t in temps}
    for s in isothermal:
        a, _ = _shifted_endpoints(s, shift)
        key = round(a, 6)
        iso_load[key] = iso_load.get(key, 0.0) + (-s.duty_mw)   # hot +, cold -

    def sensible_surplus(t_lo: float, t_hi: float) -> float:
        cp_hot = cp_cold = 0.0
        for s in sensible:
            a, b = _shifted_endpoints(s, shift)
            s_hi, s_lo = max(a, b), min(a, b)
            if s_lo <= t_lo and s_hi >= t_hi:
                if s.kind == "hot":
                    cp_hot += s.cp_mw_per_c
                else:
                    cp_cold += s.cp_mw_per_c
        return (cp_hot - cp_cold) * (t_hi - t_lo)

    h = iso_load.get(temps[0], 0.0)
    nodes: Curve = [(temps[0], h)]
    for i in range(len(temps) - 1):
        t_hi, t_lo = temps[i], temps[i + 1]
        h += sensible_surplus(t_lo, t_hi)
        h += iso_load.get(t_lo, 0.0)
        nodes.append((t_lo, h))

    h_values = [hv for _, hv in nodes]
    q_hmin = max(0.0, -min(h_values))
    feasible = [(t, hv + q_hmin) for t, hv in nodes]
    q_cmin = feasible[-1][1]
    pinch_t = min(feasible, key=lambda p: p[1])[0]
    max_recovery = total_hot - q_cmin

    return PinchResult(
        pinch_temperature_c=pinch_t,
        min_hot_utility_mw=q_hmin,
        min_cold_utility_mw=q_cmin,
        max_recovery_mw=max_recovery,
        grand_composite=feasible,
        hot_composite=hot_c,
        cold_composite=cold_c,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pixi run python -m pytest tests/unit/test_pinch.py --basetemp=.pytest_tmp -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add aspen_automation/heat_integration/pinch.py tests/unit/test_pinch.py
git commit -m "feat(heat-integration): Problem Table Algorithm with composite curves"
```

---

## Task 4: Utility targeting (steam raising + turbine power)

**Files:**
- Create: `aspen_automation/heat_integration/utility_targeting.py`
- Test: `tests/unit/test_utility_targeting.py`

Steam is **raised below the pinch** (the process is a heat source there). A steam level is a cold sink, so its saturation temperature shifts **up** by ΔTmin/2 before being placed on the grand composite curve. The cumulative heat raisable down to a level = the GCC value `H` at that shifted temperature; per-level = cumulative minus the next-hotter level. Each raised parcel expands through a turbine from its saturation temperature to the condenser temperature; shaft work = `efficiency · Q · (1 − T_cond/T_sat)` (Kelvin Carnot factor). `net_power = compressor_work − turbine_power` (+ import, − export).

> Note: this corrects a reversed parenthetical in the spec ("raise steam (above pinch)"). Steam raising is thermodynamically a below-pinch activity; heating demand is above the pinch.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_utility_targeting.py
import pytest

from aspen_automation.heat_integration.config import SteamLevel
from aspen_automation.heat_integration.pinch import PinchResult
from aspen_automation.heat_integration.utility_targeting import target_utilities


def _pinch():
    # pinch at shifted 100 C; below-pinch branch (100,0)->(50,200)->(20,300)
    gcc = [(150.0, 80.0), (100.0, 0.0), (50.0, 200.0), (20.0, 300.0)]
    return PinchResult(
        pinch_temperature_c=100.0,
        min_hot_utility_mw=80.0,
        min_cold_utility_mw=300.0,
        max_recovery_mw=0.0,
        grand_composite=gcc,
        hot_composite=[],
        cold_composite=[],
    )


def test_single_level_steam_raised_and_turbine_power():
    r = target_utilities(
        _pinch(),
        steam_levels=[SteamLevel("MP", 45.0, 40.0)],
        compressor_work_mw=5.0,
        turbine_efficiency=0.8,
        condenser_temp_c=20.0,
        dt_min=10.0,
    )
    assert r.steam_raised_by_level["MP"] == pytest.approx(200.0)
    # 0.8 * 200 * (1 - 293.15/318.15)
    assert r.turbine_power_mw == pytest.approx(12.5726, abs=1e-3)
    assert r.compressor_work_mw == pytest.approx(5.0)
    assert r.net_power_mw == pytest.approx(5.0 - 12.5726, abs=1e-3)


def test_level_above_pinch_raises_no_steam():
    r = target_utilities(
        _pinch(),
        steam_levels=[SteamLevel("HP", 200.0, 100.0)],  # shifted 205 > pinch 100
        compressor_work_mw=0.0,
        turbine_efficiency=0.8,
        condenser_temp_c=20.0,
        dt_min=10.0,
    )
    assert r.steam_raised_by_level["HP"] == pytest.approx(0.0)
    assert r.turbine_power_mw == pytest.approx(0.0)


def test_two_levels_allocate_incrementally_hottest_first():
    # MP shifted 75 -> H=100 (interp between (100,0),(50,200))
    # LP shifted 23 -> H=290 (interp between (50,200),(20,300): 300 + 0.1*(200-300))
    r = target_utilities(
        _pinch(),
        steam_levels=[SteamLevel("MP", 70.0, 40.0), SteamLevel("LP", 18.0, 6.0)],
        compressor_work_mw=0.0,
        turbine_efficiency=0.8,
        condenser_temp_c=15.0,
        dt_min=10.0,
    )
    assert r.steam_raised_by_level["MP"] == pytest.approx(100.0)
    assert r.steam_raised_by_level["LP"] == pytest.approx(190.0)  # 290 - 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pixi run python -m pytest tests/unit/test_utility_targeting.py --basetemp=.pytest_tmp -q`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement `utility_targeting.py`**

```python
"""Steam-level raising + turbine power balance from the grand composite curve."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .config import SteamLevel
from .pinch import Curve, PinchResult

KELVIN = 273.15


@dataclass(frozen=True)
class UtilityTarget:
    steam_raised_by_level: Dict[str, float]
    turbine_power_mw: float
    compressor_work_mw: float
    net_power_mw: float


def _interp_gcc(gcc: Curve, t: float) -> float:
    """Linear interpolation of H at shifted temperature ``t``; gcc sorted T descending."""
    if not gcc:
        return 0.0
    if t >= gcc[0][0]:
        return gcc[0][1]
    if t <= gcc[-1][0]:
        return gcc[-1][1]
    for (t_hi, h_hi), (t_lo, h_lo) in zip(gcc, gcc[1:]):
        if t_lo <= t <= t_hi:
            if t_hi == t_lo:
                return h_lo
            frac = (t - t_lo) / (t_hi - t_lo)
            return h_lo + frac * (h_hi - h_lo)
    return gcc[-1][1]


def target_utilities(
    pinch_result: PinchResult,
    steam_levels: List[SteamLevel],
    compressor_work_mw: float,
    turbine_efficiency: float,
    condenser_temp_c: float,
    dt_min: float,
) -> UtilityTarget:
    shift = dt_min / 2.0
    pinch_t = pinch_result.pinch_temperature_c
    gcc = pinch_result.grand_composite

    levels_hot_first = sorted(steam_levels, key=lambda lv: lv.t_sat_c, reverse=True)
    raised: Dict[str, float] = {}
    prev_cumulative = 0.0
    for lv in levels_hot_first:
        t_shifted = lv.t_sat_c + shift          # steam is a cold sink -> shift up
        if t_shifted >= pinch_t:
            raised[lv.name] = 0.0               # above pinch: not a raising region
            continue
        cumulative = _interp_gcc(gcc, t_shifted)
        raised[lv.name] = max(0.0, cumulative - prev_cumulative)
        prev_cumulative = cumulative

    turbine = 0.0
    for lv in levels_hot_first:
        q = raised.get(lv.name, 0.0)
        if q <= 0.0:
            continue
        carnot = 1.0 - (condenser_temp_c + KELVIN) / (lv.t_sat_c + KELVIN)
        turbine += turbine_efficiency * q * max(0.0, carnot)

    net = compressor_work_mw - turbine
    return UtilityTarget(raised, turbine, compressor_work_mw, net)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pixi run python -m pytest tests/unit/test_utility_targeting.py --basetemp=.pytest_tmp -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add aspen_automation/heat_integration/utility_targeting.py tests/unit/test_utility_targeting.py
git commit -m "feat(heat-integration): steam-level raising and turbine power balance"
```

---

## Task 5: Energy KPI builder + orchestrator + extractor wiring

**Files:**
- Create: `aspen_automation/heat_integration/energy_kpi.py`
- Modify: `aspen_automation/heat_integration/__init__.py` (add `analyze_heat_integration`, `_compressor_work_mw`)
- Modify: `aspen_automation/extractor.py` (~lines 1209-1226 in `calculate_kpis`)
- Test: `tests/unit/test_energy_kpi.py`

`energy_consumption_mw` (redefined) = `min_hot_utility_mw + net_power_mw`. The gross Σ|duty| number is preserved as `energy.gross_abs_duty_mw`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_energy_kpi.py
import pytest

from aspen_automation.heat_integration.energy_kpi import build_energy_kpi
from aspen_automation.heat_integration.pinch import PinchResult
from aspen_automation.heat_integration.thermal_streams import ThermalStream
from aspen_automation.heat_integration.utility_targeting import UtilityTarget


def test_build_energy_kpi_shape_and_formula():
    streams = [
        ThermalStream("HOT", 200.0, 40.0, -480.0, "hot", False),
        ThermalStream("COLD", 30.0, 180.0, 300.0, "cold", False),
    ]
    pinch = PinchResult(55.0, 190.0, 40.0, 550.0, [(55.0, 0.0)], [], [])
    util = UtilityTarget({"HP": 100.0}, 30.0, 5.0, -25.0)

    kpi = build_energy_kpi(streams, pinch, util, dt_min=10.0)

    # redefined headline = Q_Hmin + net_power
    assert kpi["energy_consumption_mw"] == pytest.approx(190.0 + (-25.0))
    e = kpi["energy"]
    assert e["gross_heating_mw"] == pytest.approx(300.0)
    assert e["gross_cooling_mw"] == pytest.approx(-480.0)
    assert e["net_duty_mw"] == pytest.approx(-180.0)
    assert e["gross_abs_duty_mw"] == pytest.approx(780.0)
    assert e["integrated"]["dt_min_c"] == 10.0
    assert e["integrated"]["pinch_temperature_c"] == pytest.approx(55.0)
    assert e["integrated"]["max_recovery_mw"] == pytest.approx(550.0)
    assert e["steam_power"]["net_power_mw"] == pytest.approx(-25.0)
    assert e["steam_power"]["steam_raised_by_level"] == {"HP": 100.0}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pixi run python -m pytest tests/unit/test_energy_kpi.py --basetemp=.pytest_tmp -q`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement `energy_kpi.py`**

```python
"""Redefine the energy KPI from pinch + power targets; preserve the gross Σ|duty| value."""
from __future__ import annotations

from typing import Any, Dict, List

from .pinch import PinchResult
from .thermal_streams import ThermalStream
from .utility_targeting import UtilityTarget


def build_energy_kpi(
    thermal_streams: List[ThermalStream],
    pinch_result: PinchResult,
    utility_target: UtilityTarget,
    dt_min: float,
) -> Dict[str, Any]:
    gross_heating = sum(s.duty_mw for s in thermal_streams if s.kind == "cold")
    gross_cooling = sum(s.duty_mw for s in thermal_streams if s.kind == "hot")
    gross_abs = sum(abs(s.duty_mw) for s in thermal_streams)
    net_duty = gross_heating + gross_cooling
    energy_consumption = pinch_result.min_hot_utility_mw + utility_target.net_power_mw
    return {
        "energy": {
            "gross_heating_mw": gross_heating,
            "gross_cooling_mw": gross_cooling,
            "net_duty_mw": net_duty,
            "gross_abs_duty_mw": gross_abs,
            "integrated": {
                "dt_min_c": dt_min,
                "pinch_temperature_c": pinch_result.pinch_temperature_c,
                "min_hot_utility_mw": pinch_result.min_hot_utility_mw,
                "min_cold_utility_mw": pinch_result.min_cold_utility_mw,
                "max_recovery_mw": pinch_result.max_recovery_mw,
            },
            "steam_power": {
                "steam_raised_by_level": dict(utility_target.steam_raised_by_level),
                "turbine_power_mw": utility_target.turbine_power_mw,
                "compressor_work_mw": utility_target.compressor_work_mw,
                "net_power_mw": utility_target.net_power_mw,
            },
        },
        "energy_consumption_mw": energy_consumption,
    }
```

- [ ] **Step 4: Implement the orchestrator in `__init__.py`**

Replace the contents of `aspen_automation/heat_integration/__init__.py` with:

```python
"""Heat-integration pinch analysis (post-processing on converged run artifacts)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from .config import HeatIntegrationConfig, SteamLevel
from .energy_kpi import build_energy_kpi
from .pinch import PinchResult, build_composite_curves, pinch_analysis
from .thermal_streams import ThermalStream, extract_thermal_streams
from .utility_targeting import UtilityTarget, target_utilities

__all__ = [
    "HeatIntegrationConfig",
    "SteamLevel",
    "ThermalStream",
    "PinchResult",
    "UtilityTarget",
    "pinch_analysis",
    "build_composite_curves",
    "extract_thermal_streams",
    "target_utilities",
    "build_energy_kpi",
    "analyze_heat_integration",
    "figures_for_run",
]


def _compressor_work_mw(blocks_df: pd.DataFrame) -> float:
    if "block_type" not in blocks_df.columns or "net_work_mw" not in blocks_df.columns:
        return 0.0
    mask = blocks_df["block_type"].astype(str).str.upper() == "COMPR"
    vals = pd.to_numeric(blocks_df.loc[mask, "net_work_mw"], errors="coerce").dropna()
    return float(vals.sum())


def analyze_heat_integration(
    blocks_df: pd.DataFrame,
    streams_df: pd.DataFrame,
    spec_dict: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Run the full pinch chain; return the energy-KPI dict, or ``None`` if no streams."""
    config = HeatIntegrationConfig.from_spec(spec_dict)
    flowsheet = (spec_dict or {}).get("flowsheet") or []
    streams = extract_thermal_streams(blocks_df, streams_df, flowsheet)
    if not streams:
        return None
    pinch = pinch_analysis(streams, config.dt_min_c)
    util = target_utilities(
        pinch,
        config.steam_levels,
        _compressor_work_mw(blocks_df),
        config.turbine_efficiency,
        config.condenser_temp_c,
        config.dt_min_c,
    )
    return build_energy_kpi(streams, pinch, util, config.dt_min_c)


def figures_for_run(results_dir: Any, spec_dict: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Recompute the pinch result from a run's CSVs and return composite/GCC figures."""
    from . import heat_integration_figures as hif

    rd = Path(results_dir)
    blocks_df = pd.read_csv(rd / "blocks.csv")
    streams_df = pd.read_csv(rd / "streams.csv")
    config = HeatIntegrationConfig.from_spec(spec_dict)
    flowsheet = (spec_dict or {}).get("flowsheet") or []
    streams = extract_thermal_streams(blocks_df, streams_df, flowsheet)
    if not streams:
        return {}
    pinch = pinch_analysis(streams, config.dt_min_c)
    return {
        "heat_composite_curves": hif.fig_composite_curves(
            pinch.hot_composite, pinch.cold_composite
        ),
        "heat_grand_composite": hif.fig_grand_composite(
            pinch.grand_composite, config.steam_levels, config.dt_min_c
        ),
    }
```

> `figures_for_run` imports `heat_integration_figures` lazily; it is exercised in Task 6. `analyze_heat_integration` does not depend on it.

- [ ] **Step 5: Run the KPI + orchestrator tests**

Run: `pixi run python -m pytest tests/unit/test_energy_kpi.py --basetemp=.pytest_tmp -q`
Expected: PASS (1 passed)

- [ ] **Step 6: Wire the orchestrator into `extractor.py`**

In `aspen_automation/extractor.py`, inside `calculate_kpis`, replace these two lines (currently ~1209-1210):

```python
    duty_mw = _numeric_series(blocks_df, "duty_mw").dropna()
    energy_consumption_mw = float(duty_mw.abs().sum()) if not duty_mw.empty else 0.0
```

with:

```python
    duty_mw = _numeric_series(blocks_df, "duty_mw").dropna()
    energy_consumption_mw = float(duty_mw.abs().sum()) if not duty_mw.empty else 0.0
    energy_block: Optional[Dict[str, Any]] = None
    try:
        from .heat_integration import analyze_heat_integration

        heat = analyze_heat_integration(blocks_df, streams_df, spec_dict)
        if heat is not None:
            energy_block = heat["energy"]
            energy_consumption_mw = heat["energy_consumption_mw"]
    except Exception as exc:  # pragma: no cover - defensive: never break KPI extraction
        energy_block = {"available": False, "reason": f"heat integration unavailable: {exc}"}
```

Then, in the `return { ... }` dict at the end of `calculate_kpis` (the dict that currently ends with `"synthesis_loop": synthesis_loop,`), change the return so the `energy` block is attached. Replace:

```python
    return {
        "production_rate_tpd": production_rate_tpd,
        "product_stream": product_stream_name,
        "product_total_tpd": product_total_tpd,
        "product_component": yield_component,
        "product_component_tpd": product_component_tpd,
        "methanol_tpd": methanol_tpd,
        "purity_fraction": purity_fraction,
        "energy_consumption_mw": energy_consumption_mw,
        "energy_unit_basis": _energy_unit_basis(),
        "yield_fraction": yield_fraction,
        "convergence_status": diagnostics.get("convergence_status", "unknown"),
        "synthesis_loop": synthesis_loop,
    }
```

with:

```python
    kpis: Dict[str, Any] = {
        "production_rate_tpd": production_rate_tpd,
        "product_stream": product_stream_name,
        "product_total_tpd": product_total_tpd,
        "product_component": yield_component,
        "product_component_tpd": product_component_tpd,
        "methanol_tpd": methanol_tpd,
        "purity_fraction": purity_fraction,
        "energy_consumption_mw": energy_consumption_mw,
        "energy_unit_basis": _energy_unit_basis(),
        "yield_fraction": yield_fraction,
        "convergence_status": diagnostics.get("convergence_status", "unknown"),
        "synthesis_loop": synthesis_loop,
    }
    if energy_block is not None:
        kpis["energy"] = energy_block
    return kpis
```

(`Dict`, `Any`, `Optional` are already imported in extractor.py.)

- [ ] **Step 7: Run the full unit suite to confirm no regression**

Run: `pixi run python -m pytest tests/unit --basetemp=.pytest_tmp -q`
Expected: the 3 known pre-existing failures only (lights_recovery + 2 reactor-sweep); everything else passes, no new failures, no import errors.

- [ ] **Step 8: Commit**

```bash
git add aspen_automation/heat_integration/energy_kpi.py aspen_automation/heat_integration/__init__.py aspen_automation/extractor.py tests/unit/test_energy_kpi.py
git commit -m "feat(heat-integration): redefine energy KPI and wire into extractor"
```

---

## Task 6: Figures + dashboard wiring

**Files:**
- Create: `aspen_automation/heat_integration/heat_integration_figures.py`
- Modify: `aspen_automation/dashboard.py` (`save_dashboard_figures`)
- Test: `tests/unit/test_heat_integration_figures.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_heat_integration_figures.py
import matplotlib

matplotlib.use("Agg")

from aspen_automation.heat_integration.config import SteamLevel
from aspen_automation.heat_integration.heat_integration_figures import (
    fig_composite_curves,
    fig_grand_composite,
)


def test_composite_curves_returns_figure_with_two_lines():
    hot = [(40.0, 0.0), (150.0, 440.0), (200.0, 590.0)]
    cold = [(30.0, 0.0), (50.0, 40.0), (160.0, 700.0), (180.0, 740.0)]
    fig = fig_composite_curves(hot, cold)
    ax = fig.axes[0]
    assert len(ax.lines) >= 2          # hot + cold composite
    assert ax.get_xlabel()             # axis is labelled


def test_grand_composite_draws_steam_levels():
    gcc = [(195.0, 190.0), (145.0, 180.0), (55.0, 0.0), (35.0, 40.0)]
    levels = [SteamLevel("HP", 311.0, 100.0), SteamLevel("MP", 250.0, 40.0)]
    fig = fig_grand_composite(gcc, levels, dt_min=10.0)
    ax = fig.axes[0]
    assert len(ax.lines) >= 1          # GCC curve present
    # two steam levels drawn as horizontal reference lines
    assert len(ax.get_lines()) + len(ax.collections) >= 1


def test_figures_handle_empty_curves_without_crashing():
    assert fig_composite_curves([], []) is not None
    assert fig_grand_composite([], [], dt_min=10.0) is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pixi run python -m pytest tests/unit/test_heat_integration_figures.py --basetemp=.pytest_tmp -q`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: Implement `heat_integration_figures.py`**

```python
"""Composite-curve and grand-composite-curve figures (Nature style)."""
from __future__ import annotations

from typing import List, Sequence, Tuple

from .. import figure_style
from .config import SteamLevel

Curve = Sequence[Tuple[float, float]]


def fig_composite_curves(hot_composite: Curve, cold_composite: Curve):
    figure_style.use_nature_style()
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(3.4, 2.6))
    if hot_composite:
        ht = [t for t, _ in hot_composite]
        hh = [h for _, h in hot_composite]
        ax.plot(hh, ht, color="#c0392b", lw=1.2, label="Hot composite")
    if cold_composite:
        ct = [t for t, _ in cold_composite]
        ch = [h for _, h in cold_composite]
        ax.plot(ch, ct, color="#2471a3", lw=1.2, label="Cold composite")
    ax.set_xlabel("Enthalpy (MW)")
    ax.set_ylabel("Temperature (°C)")
    ax.set_title("Composite curves")
    if hot_composite or cold_composite:
        ax.legend(frameon=False, loc="best")
    fig.tight_layout()
    return fig


def fig_grand_composite(grand_composite: Curve, steam_levels: List[SteamLevel], dt_min: float):
    figure_style.use_nature_style()
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(3.4, 2.6))
    if grand_composite:
        gt = [t for t, _ in grand_composite]
        gh = [h for _, h in grand_composite]
        ax.plot(gh, gt, color="#1e8449", lw=1.2, label="Grand composite")
        shift = dt_min / 2.0
        for lv in steam_levels or []:
            ax.axhline(lv.t_sat_c + shift, color="#7f8c8d", lw=0.6, ls="--")
            ax.text(
                max(gh) if gh else 0.0,
                lv.t_sat_c + shift,
                f" {lv.name}",
                fontsize=6,
                va="center",
                color="#7f8c8d",
            )
    ax.set_xlabel("Net heat flow (MW)")
    ax.set_ylabel("Shifted temperature (°C)")
    ax.set_title("Grand composite curve")
    fig.tight_layout()
    return fig
```

- [ ] **Step 4: Run figure test to verify it passes**

Run: `pixi run python -m pytest tests/unit/test_heat_integration_figures.py --basetemp=.pytest_tmp -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Wire the figures into `save_dashboard_figures`**

In `aspen_automation/dashboard.py`, inside `save_dashboard_figures`, immediately **before** the final `return out`, add this guarded block (it reuses the already-defined `figdir`, `spec`, `results_dir`, `out`, and the `plt` imported just above):

```python
    try:
        from .heat_integration import figures_for_run

        for name, fig in figures_for_run(results_dir, spec).items():
            for ext in ("svg", "pdf"):
                path = figdir / f"{name}.{ext}"
                fig.savefig(str(path), bbox_inches="tight")
                out[f"{name}_{ext}"] = path
            plt.close(fig)
    except Exception as exc:  # pragma: no cover - never break the dashboard
        print(f"Heat-integration figures skipped ({exc}).")
```

- [ ] **Step 6: Run dashboard unit tests to confirm no regression**

Run: `pixi run python -m pytest tests/unit/test_dashboard.py --basetemp=.pytest_tmp -q`
Expected: PASS (same as baseline — these pass with `--basetemp`).

- [ ] **Step 7: Commit**

```bash
git add aspen_automation/heat_integration/heat_integration_figures.py aspen_automation/dashboard.py tests/unit/test_heat_integration_figures.py
git commit -m "feat(heat-integration): composite/grand-composite figures and dashboard wiring"
```

---

## Task 7: Integration sanity test on the LHHW run

**Files:**
- Test: `tests/integration/test_heat_integration_pipeline.py`

Runs the whole chain on the committed LHHW fixture and asserts the deterministic gross numbers (independent of the pinch algorithm) plus thermodynamic invariants. Expected gross values, computed directly from `blocks.csv`:
- `gross_abs_duty_mw ≈ 3641.74` (equals the *old* `energy_consumption_mw` in `kpis.json` — energy-balance closure).
- `gross_heating_mw ≈ 912.98` (B-DEGAS 231.31 + B-DIST-REB 612.94 + B-PDEG 36.60 + B-ATR 32.13).
- `gross_cooling_mw ≈ −2728.76` (B-COOL + B-SYN + B-SEP + B-LCOOL + B-DIST-COND + B-VFLA).

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_heat_integration_pipeline.py
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from aspen_automation.heat_integration import analyze_heat_integration

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "lhhw_run"
SPEC_YAML = (
    Path(__file__).resolve().parents[2]
    / "process_library" / "methanol" / "process.yaml"
)


def _load():
    blocks_df = pd.read_csv(FIXTURE / "blocks.csv")
    streams_df = pd.read_csv(FIXTURE / "streams.csv")
    spec_dict = yaml.safe_load(SPEC_YAML.read_text(encoding="utf-8"))
    return blocks_df, streams_df, spec_dict


def test_pipeline_gross_numbers_match_run():
    blocks_df, streams_df, spec_dict = _load()
    kpi = analyze_heat_integration(blocks_df, streams_df, spec_dict)
    assert kpi is not None
    e = kpi["energy"]

    old_energy = json.loads((FIXTURE / "kpis.json").read_text())["energy_consumption_mw"]
    assert e["gross_abs_duty_mw"] == pytest.approx(old_energy, abs=1.0)
    assert e["gross_abs_duty_mw"] == pytest.approx(3641.74, abs=1.0)
    assert e["gross_heating_mw"] == pytest.approx(912.98, abs=1.0)
    assert e["gross_cooling_mw"] == pytest.approx(-2728.76, abs=1.0)


def test_pipeline_targets_are_thermodynamically_sane():
    blocks_df, streams_df, spec_dict = _load()
    kpi = analyze_heat_integration(blocks_df, streams_df, spec_dict)
    e = kpi["energy"]
    integ = e["integrated"]

    assert integ["min_hot_utility_mw"] >= 0.0
    assert integ["min_cold_utility_mw"] >= 0.0
    assert integ["max_recovery_mw"] >= 0.0
    # cannot need more hot utility than the total heating demand
    assert integ["min_hot_utility_mw"] <= e["gross_heating_mw"] + 1e-6
    # the integrated headline is far smaller in magnitude than the gross Σ|duty|
    assert abs(kpi["energy_consumption_mw"]) < e["gross_abs_duty_mw"]


def test_pipeline_reads_compressor_work_from_blocks():
    blocks_df, streams_df, spec_dict = _load()
    kpi = analyze_heat_integration(blocks_df, streams_df, spec_dict)
    # B-COMP net_work_mw in the fixture is ~0.3087 MW
    assert kpi["energy"]["steam_power"]["compressor_work_mw"] == pytest.approx(0.3087, abs=1e-3)
```

- [ ] **Step 2: Run test to verify it fails first, then passes**

Run: `pixi run python -m pytest tests/integration/test_heat_integration_pipeline.py --basetemp=.pytest_tmp -q`
Expected: PASS (3 passed) — all dependencies already exist from Tasks 1-5. (If the gross numbers are off, the bug is in `thermal_streams` classification, not the test.)

- [ ] **Step 3: Run the entire test suite for a final regression check**

Run: `pixi run python -m pytest tests/unit tests/integration --basetemp=.pytest_tmp -q`
Expected: only the 3 known pre-existing failures; all new heat-integration tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_heat_integration_pipeline.py
git commit -m "test(heat-integration): integration sanity test on LHHW run artifacts"
```

---

## Done

After Task 7, the package replaces the Σ|duty| headline with `Q_Hmin + net_power` and exposes a structured `energy` block (gross reality + integrated targets + steam/power), with composite/GCC figures in the dashboard. Hand the branch to `superpowers:finishing-a-development-branch`.
