# INP Generation Guide

This document describes the process of generating Aspen Plus Input (`.inp`) files from the internal `PlantSpecification` model. The `generate_inp` function translates a validated specification into the canonical Aspen Plus INP syntax and formatting.

## Core Function: `generate_inp`

```python
from aspen_automation import load_spec, generate_inp

spec = load_spec("specs/methanol_plant.yaml")
inp_content = generate_inp(spec)

with open("output.inp", "w", encoding="utf-8") as f:
    f.write(inp_content)
```

### Signature

`generate_inp(spec: PlantSpecification | dict, output_path: Optional[str] = None) -> str`

- **spec**: A validated `PlantSpecification` object or equivalent dictionary.
- **output_path**: Optional file path to write the result.
- **Returns**: The complete string content of the INP file.

---

## Section Order

The generator emits sections in the required order:

1. `TITLE`
2. `IN-UNITS`
3. `DEF-STREAMS`
4. `DATABANKS`
5. `PROP-SOURCES`
6. `COMPONENTS`
7. `PROPERTIES`
8. `FLOWSHEET`
9. `STREAM`
10. `BLOCK`
11. `CHEMISTRY` (optional)
12. `REACTIONS` (optional)

---

## Formatting Rules

### TITLE
- Always single-quoted: `TITLE 'My Plant'`.
- A blank line follows the title section.
- If `metadata.description` is provided, it is emitted as `;` comment lines above the title.

### IN-UNITS
- Uses Aspen keywords in uppercase.
- Flow units are quoted.

Example:
```inp
IN-UNITS MET PRESSURE=BAR TEMPERATURE=C MASS-FLOW='KG/HR' MOLE-FLOW='KG/HR'
```

### DEF-STREAMS
- Fixed format: `DEF-STREAMS CONVEN ALL`.

### DATABANKS and PROP-SOURCES
- Each databank is single-quoted.
- Continuation lines use `&`.
- Databanks listed in `properties.binary_parameters[*].databanks` are merged into
  the same `DATABANKS`/`PROP-SOURCES` flow. For the methanol NRTL screening case,
  `APV140 VLE-IG`, `APV140 VLE-LIT`, and `APV140 LLE-ASPEN` are used as the
  verified Aspen V14 source path for the CH3OH/H2O binary interaction parameters.
- The generator does not emit unverified numeric NRTL interaction parameters.
  Explicit values should only be added after their Aspen V14 batch syntax and
  units are source-verified.

Example:
```inp
DATABANKS 'APV140 PURE32' / 'APV140 AQUEOUS' / 'APV140 SOLIDS' / &
        'APV140 INORGANIC' / 'APV140 VLE-IG' / 'APV140 VLE-LIT' / &
        'APV140 LLE-ASPEN' / 'NOASPENPCD'

PROP-SOURCES 'APV140 PURE32' / 'APV140 AQUEOUS' / 'APV140 SOLIDS' / &
        'APV140 INORGANIC' / 'APV140 VLE-IG' / 'APV140 VLE-LIT' / &
        'APV140 LLE-ASPEN'
```

### COMPONENTS
- 4-space indentation for entries.
- Each line ends with `/`.

Example:
```inp
COMPONENTS
    CH4 METHANE /
    H2O WATER H2O /
```

### PROPERTIES
- Single-line format: `PROPERTIES RK-SOAVE`.

### FLOWSHEET
- `IN=` and `OUT=` list the first stream with the keyword, followed by space-separated streams.

Example:
```inp
FLOWSHEET
    BLOCK MIX-FEED IN=NG-FEED STEAM O2-FEED OUT=ATR-IN
```

### STREAM
- Always includes `SUBSTREAM MIXED`.
- Temperature/pressure and flow values are on a continuation line.
- The generator always emits `MOLE-FRAC` for composition.

Example:
```inp
STREAM NG-FEED
    SUBSTREAM MIXED TEMP=40 PRES=30 &
        MASS-FLOW=220000
    MOLE-FRAC
        CH4 1.0 /
```

### BLOCK
- Standard block parameters use a `PARAM` block with 8-space indentation.

Example:
```inp
BLOCK B-ATR RGIBBS
    PARAM
        TEMP=1000
        PRES=30
```

### Special Block Types

**FSPLIT** uses `FRAC` instead of `PARAM`:
```inp
BLOCK SPLIT FSPLIT
    FRAC RECYCLE 0.95
    FRAC PURGE 0.05
```

**SEP** uses `FRAC` with stream, substream, and component identifiers:
```inp
BLOCK B-DIST SEP
    PARAM
    FRAC STRM=MEOH-PRO SUBSTRM=MIXED COMP=CH3OH FRAC=0.99
```

**VALVE** is emitted for pressure letdown with an explicit outlet pressure:
```inp
BLOCK B-DP VALVE
    PARAM P-OUT=1.8
```

For the canonical methanol process, the pressure letdown is followed by a
low-pressure `FLASH2` stabilizer (`B-DEGAS`) before the final methanol/water
column. This removes dissolved light gases with ordinary block syntax:
```inp
BLOCK B-DEGAS FLASH2
    PARAM TEMP=80.0 PRES=0.0
```

**RADFRAC** is supported only when the YAML block has a complete `radfrac`
payload and the flowsheet has exactly one feed and two material products. The
current Aspen V14 batch form is:
```inp
BLOCK B-DIST RADFRAC
    PARAM NSTAGE=30 ALGORITHM=STANDARD MAXOL=50 DAMPING=NONE
    COL-CONFIG CONDENSER=TOTAL
    FEEDS CRUDE-LQ 16
    PRODUCTS MEOH-PRO 1 L / WASTE-H2O 30 L
    P-SPEC 1 1.5
    COL-SPECS DP-COL=0.58 MASS-B=68000.0 MASS-RR=2.0
    TRAY-REPORT TRAY-OPTION=ALL-TRAYS
```

### CHEMISTRY
- Stoichiometry entries use `&` continuation and `/` terminators.

Example:
```inp
CHEMISTRY GLOBAL
    STOIC 1 &
        CO -1 / &
        H2 -2 / &
        CH3OH 1 /
```

### REACTIONS
- Links reaction sets to Aspen block types.

Example:
```inp
REACTIONS RXN-SET1 REQUIL
    REAC-DATA 1
    REAC-DATA 2
```

---

## Troubleshooting

- **Missing `/` terminators**: Aspen rejects COMPONENTS and composition lines without `/`.
- **Unbalanced quotes**: DATABANKS and PROP-SOURCES require single-quoted names.
- **Continuation errors**: A line ending in `&` must be followed by an indented continuation line.
- **Missing SUBSTREAM**: Each STREAM definition must include `SUBSTREAM MIXED`.
- **PARAM placement**: Parameter assignments require a preceding `PARAM` line (except FSPLIT).

---

## Canonical Reference

For a complete example of the target output format, refer to:
`legacy_old_files/archive/aspen_artifacts/Methanol Plant/MethanolPlant.inp`

This file serves as the canonical reference for all generated structure and syntax.
