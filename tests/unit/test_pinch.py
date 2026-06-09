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
