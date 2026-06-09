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
