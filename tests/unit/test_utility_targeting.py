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
