# Methanol Plant Templates

## methanol_plant_atr.yaml

`methanol_plant_atr.yaml` is a 10,000 tonnes per day (TPD) methanol plant template using an Autothermal Reforming (ATR) front end and a recycle-based synthesis loop.

### Design Basis

- Capacity: 10,000 TPD methanol
- Product quality target: Grade AA methanol (>= 99.85 wt%)
- Feedstock basis: natural gas (CH4), steam, and oxygen
- Property method: RK-SOAVE

Reference files:
- `archive/aspen_artifacts/Methanol Plant/MethanolPlant.inp`
- `archive/aspen_artifacts/Methanol Plant/DESIGN_BASIS.md`

### Process Sections

1. Reforming: `MIX-FEED -> B-ATR -> B-COOL -> B-FLASH`
2. Compression: `B-COMP`
3. Synthesis loop: `MIX-LOOP -> B-SYN -> B-SEP -> SPLIT`
4. Purification: `B-DIST`

### Key Operating Conditions

- ATR reactor (`B-ATR`): 1000 C, 30 bar
- Synthesis reactor (`B-SYN`): 250 C, 80 bar
- Compressor (`B-COMP`) discharge pressure: 80 bar
- Recycle split target (`SPLIT`): 95% recycle

### Customization Guide

1. Change plant capacity by scaling feed stream flow rates (`NG-FEED`, `STEAM`, `O2-FEED`).
2. Tune operating conditions in `blocks[*].parameters`.
3. Modify feed compositions in `streams[*].composition`.
4. Adjust acceptance thresholds in `targets` (`production_rate_tpd`, `tolerance`, `purity.min_value`).

### Usage

```python
from aspen_automation import run_simulation, load_template

# Load by template name (or use load_spec with a file path)
spec = load_template("methanol_plant_atr")

results = run_simulation(
    spec,
    build_mode="auto",
    output_dir="results/",
    visible=False,
)

print(results["kpis"]["convergence_status"])
print(results["kpis"]["production_rate_tpd"])
print(results["acceptance"]["passed"])
print(results["report_dir"])
```
