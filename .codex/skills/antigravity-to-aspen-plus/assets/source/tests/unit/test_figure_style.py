import matplotlib
matplotlib.use("Agg")  # headless

from aspen_automation.figure_style import use_nature_style, fig_synthesis_loop


def test_use_nature_style_does_not_raise():
    use_nature_style()  # must work even if SciencePlots/LaTeX absent


def test_fig_synthesis_loop_returns_figure_with_bars():
    data = {"kpis": {"synthesis_loop": {
        "co_conversion_fraction": 0.34,
        "co2_conversion_fraction": 0.12,
        "h2_consumption_fraction": 0.40,
    }}}
    fig = fig_synthesis_loop(data)
    ax = fig.axes[0]
    assert len(ax.patches) == 3  # three bars
    assert ax.get_ylabel()


import pandas as pd

from aspen_automation.figure_style import fig_stream_composition, fig_kpi_summary


def test_fig_stream_composition_stacks_components():
    data = {"streams": pd.DataFrame({
        "stream_name": ["FEED", "PROD"],
        "CH4_mole_frac": [0.9, 0.0],
        "H2_mole_frac": [0.1, 0.2],
    })}
    fig = fig_stream_composition(data)
    ax = fig.axes[0]
    assert len(ax.patches) >= 2  # stacked bars across components/streams


def test_fig_kpi_summary_returns_figure():
    data = {"kpis": {"methanol_tpd": 9812, "product_total_tpd": 12000, "purity_fraction": 0.997}}
    fig = fig_kpi_summary(data)
    assert fig.axes  # has at least one axis
