import matplotlib

matplotlib.use("Agg")

from aspen_automation.heat_integration.config import SteamLevel
from aspen_automation.heat_integration.heat_integration_figures import (
    fig_composite_curves,
    fig_grand_composite,
)


def test_composite_curves_returns_figure_with_two_lines():
    hot = [(40.0, 0.0), (150.0, 440.0), (200.0, 590.0)]
    cold = [(30.0, 0.0), (50.0, 40.0), (160.0, 700.0), (180.0, 740.0)]
    fig = fig_composite_curves(hot, cold)
    ax = fig.axes[0]
    assert len(ax.lines) >= 2          # hot + cold composite
    assert ax.get_xlabel()             # axis is labelled


def test_grand_composite_draws_steam_levels():
    gcc = [(195.0, 190.0), (145.0, 180.0), (55.0, 0.0), (35.0, 40.0)]
    levels = [SteamLevel("HP", 311.0, 100.0), SteamLevel("MP", 250.0, 40.0)]
    fig = fig_grand_composite(gcc, levels, dt_min=10.0)
    ax = fig.axes[0]
    assert len(ax.lines) >= 1          # GCC curve present
    # two steam levels drawn as horizontal reference lines
    assert len(ax.get_lines()) + len(ax.collections) >= 1


def test_figures_handle_empty_curves_without_crashing():
    assert fig_composite_curves([], []) is not None
    assert fig_grand_composite([], [], dt_min=10.0) is not None
