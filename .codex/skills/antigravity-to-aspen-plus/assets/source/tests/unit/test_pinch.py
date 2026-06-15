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


def test_cold_isothermal_reboiler_needs_hot_utility():
    # Mirror of the hot-latent case for a COLD isothermal load (a RADFRAC reboiler).
    # H1/C1 balance exactly; an extra cold reboiler of 50 MW at 80 C has nothing to
    # recover from -> all 50 must come from hot utility. Guards the cold-iso sign.
    streams = [
        ThermalStream("H1", 100.0, 40.0, -120.0, "hot", False),
        ThermalStream("C1", 30.0, 90.0, 120.0, "cold", False),
        ThermalStream("CX", 80.0, 80.0, 50.0, "cold", True),
    ]
    r = pinch_analysis(streams, dt_min=10.0)
    assert r.min_hot_utility_mw == pytest.approx(50.0)
    assert r.min_cold_utility_mw == pytest.approx(0.0)


def test_composite_curve_includes_isothermal_jump():
    # A condenser (isothermal hot latent load) shows up as a vertical jump on the hot
    # composite: two points share the phase-change temperature, spanning the duty.
    streams = [
        ThermalStream("H1", 150.0, 50.0, -200.0, "hot", False),
        ThermalStream("H_COND", 100.0, 100.0, -50.0, "hot", True),
    ]
    hot, _ = build_composite_curves(streams)
    t_vals = [t for t, _ in hot]
    assert t_vals.count(100.0) == 2
    h_at_100 = [h for t, h in hot if t == 100.0]
    assert h_at_100[1] - h_at_100[0] == pytest.approx(50.0)
