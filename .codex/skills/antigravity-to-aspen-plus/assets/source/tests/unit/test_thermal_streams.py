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
