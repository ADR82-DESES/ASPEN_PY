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
