# Methanol Plant Templates

## methanol_plant_atr.yaml

`methanol_plant_atr.yaml` is a 10,000 tonnes per day (TPD) methanol plant template using an Autothermal Reforming (ATR) front end and a recycle-based synthesis loop.

### Design Basis

- Capacity: 10,000 TPD methanol
- Product quality target: Grade AA methanol (>= 99.85 wt%)
- Feedstock basis: natural gas (CH4), steam, and oxygen
- Property method: RK-SOAVE

Reference files:
- `Methanol Plant/MethanolPlant.inp`
- `Methanol Plant/DESIGN_BASIS.md`

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
from aspen_automation import load_spec, generate_inp, load_template

# Option 1: load directly from path
spec = load_spec("templates/methanol_plant_atr.yaml")

# Option 2: load by template name
spec = load_template("methanol_plant_atr")

# Generate Aspen INP content
inp_text = generate_inp(spec)
print(inp_text[:200])
```
