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
