from aspen_automation.species_colors import (
    SPECIES_PALETTE,
    species_color,
    species_color_map,
)


def test_known_species_have_distinct_stable_colors():
    ids = ["CH4", "H2O", "O2", "CO", "CO2", "H2", "CH3OH", "N2"]
    colors = [species_color(i) for i in ids]
    assert len(set(colors)) == 8  # all eight distinct
    # case-insensitive and stable
    assert species_color("CH4") == species_color("ch4") == SPECIES_PALETTE["CH4"]


def test_unknown_species_deterministic_fallback():
    first = species_color("ARGON")
    assert first.startswith("#")
    assert species_color("ARGON") == first  # deterministic / stable


def test_species_color_map_for_legend():
    m = species_color_map(["CH4", "H2O"])
    assert m == {"CH4": SPECIES_PALETTE["CH4"], "H2O": SPECIES_PALETTE["H2O"]}
