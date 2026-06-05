# pyflowsheet Spike Notes

Date: 2026-06-05  
Branch: feature/run-dashboard  
Purpose: De-risk pyflowsheet + kaleido for Aspen Dashboard v2

---

## Installed Versions

| Package       | Version  |
|---------------|----------|
| pyflowsheet   | 0.2.2    |
| scienceplots  | 2.2.1    |
| python-kaleido (kaleido) | 1.3.0 |
| matplotlib    | 3.10.9   |
| pathfinding   | 1.0.21   |

---

## pyflowsheet Class Names

All classes available at the top-level `pyflowsheet` namespace (i.e. `import pyflowsheet as pf`):

```
['BlackBox', 'Compressor', 'Distillation', 'Flowsheet', 'HeatExchanger',
 'HorizontalLabelAlignment', 'Mixer', 'PlateHex', 'Port', 'Pump', 'Splitter',
 'Stream', 'StreamFlag', 'SvgContext', 'TextElement', 'UnitOperation',
 'Valve', 'VerticalLabelAlignment', 'Vessel']
```

---

## Constructor Signatures

```python
Flowsheet(id: str, name: str, description: str = '')
BlackBox(id: str, name: str, position=(0,0), size=(20,20), description: str = '')
StreamFlag(id: str, name: str, position=(0,0), size=(40,40), description: str = '')
Mixer(id: str, name: str, position=(0,0), size=(20,20), description: str = '')
Splitter(id: str, name: str, position=(0,0), size=(20,20), description: str = '')
Distillation(id: str, name: str, hasCondenser=True, hasReboiler=True, position=(0,0), size=(40,200), description: str = '', internals=[])
Vessel(id: str, name: str, position=(0,0), size=(40,100), description: str = '', capLength=None, internals=[], angle=0, showCapLines=True)
HeatExchanger(id: str, name: str, position=(0,0), size=(40,40), description: str = '')
Compressor(id: str, name: str, position=(0,0), size=(40,40), description: str = '', internals=[])
Pump(id: str, name: str, position=(0,0), size=(40,40), description: str = '', internals=[])
Valve(id: str, name: str, position=(0,0), size=(40,20), description: str = '')
SvgContext(filename, backgroundColor=(255,255,255))
```

---

## Working pyflowsheet SVG Render Snippet

**Critical deviation from plan**: The auto-router (`_calculateAutoRoute`) crashes with
`TypeError: Pathfinder.process_node() takes from 5 to 6 positional arguments but 7 were given`
due to an API mismatch between **pyflowsheet 0.2.2** (which defines its own `process_node` with
the old 5-arg signature) and **pathfinding 1.0.21** (whose `check_neighbors` now passes `graph`
as the first positional argument, making 6 args excluding self).

**Workaround**: Set `manualRouting` on each stream before calling `draw()`. Manual routing takes
a list of `(dx, dy)` delta steps from the stream's start port.

**Also required**: Call `ctx.render(saveFile=False)` after `pfd.draw(ctx)` to serialize the SVG.
The `draw()` call alone returns the context but does not produce the string; `render()` does.
Pass `saveFile=False` when using `StringIO` as the filename to avoid `svgwrite` trying to write
to the StringIO object as a file path.

```python
from pyflowsheet import Flowsheet, BlackBox, StreamFlag, SvgContext
import io

pfd = Flowsheet('F', 'title', 'description')
a = BlackBox('A', 'Unit A', position=(100, 100), size=(60, 40))
f = StreamFlag('FEED', 'Feed', position=(0, 100))
pfd.addUnits([f, a])
pfd.connect('S1', f['Out'], a['In'])

# REQUIRED: bypass broken auto-router with manual routing steps (dx, dy list)
pfd.streams['S1'].manualRouting = [(100, 0)]

ctx = SvgContext(io.StringIO())   # filename arg accepts StringIO
pfd.draw(ctx)
svg_str = ctx.render(saveFile=False)   # saveFile=False avoids writing to StringIO path
# svg_str is a valid SVG XML string (length ~1223 bytes for this trivial diagram)
```

Output confirmed: `pyflowsheet draw OK, SVG length: 1223`

---

## Working Kaleido / Plotly Static Export Snippet

```python
import plotly.graph_objects as go

fig = go.Figure(go.Sankey(
    node=dict(label=['x', 'y']),
    link=dict(source=[0], target=[1], value=[1])
))
img_bytes = fig.to_image(format='svg')   # returns bytes
```

Output confirmed: `kaleido export OK, bytes: 2721`

`fig.to_image(format='svg')` works correctly with kaleido 1.3.0.

---

## Category → Class Mapping

| Category     | Class to use      | Notes                                           |
|--------------|-------------------|-------------------------------------------------|
| mixer        | `Mixer`           | OK                                              |
| splitter     | `Splitter`        | OK                                              |
| column       | `Distillation`    | **NOT `DistillationColumn`** — that name does not exist; use `Distillation` |
| vessel       | `Vessel`          | OK                                              |
| reactor      | `Vessel`          | OK (no dedicated Reactor class)                 |
| heater       | `HeatExchanger`   | OK                                              |
| compressor   | `Compressor`      | OK                                              |
| pump         | `Pump`            | OK                                              |
| valve        | `Valve`           | OK                                              |
| blackbox     | `BlackBox`        | OK (default fallback)                           |
| plate_hex    | `PlateHex`        | Extra class not in original mapping             |

---

## Known Issues / Concerns

1. **Auto-router is broken** (`pathfinding` 1.0.21 vs `pyflowsheet` 0.2.2 API mismatch).
   All stream connections in the dashboard renderer MUST use `manualRouting`. The auto-router
   cannot be used until either pyflowsheet is updated or pathfinding is pinned to an older
   compatible version.

   Possible fix if auto-routing is required: pin `pathfinding` to `<1.0.0` in `[pypi-dependencies]`.
   Not done here because the workaround is sufficient for the spike and the dashboard can
   pre-compute routes.

2. **`render(saveFile=False)` is required** when not writing to disk. Forgetting this call
   results in an empty string from the `SvgContext`.

3. **pyflowsheet is viable** in this environment with the manual-routing workaround. The SVG
   output is well-formed XML. Kaleido also works cleanly.

4. **Graphviz fallback**: `python-graphviz` 0.20+ is installed and importable. If the manual
   routing approach proves too cumbersome for complex diagrams, graphviz is a viable alternative.
