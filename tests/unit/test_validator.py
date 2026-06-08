import pytest
import os
import yaml
from aspen_automation.validator import validate_spec

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")

def load_fixture(name):
    path = os.path.join(FIXTURE_DIR, name)
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def test_rule1_missing_sections():
    data = {"metadata": {"title": "X", "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}}}
    # Missing components, properties, etc.
    report = validate_spec(data)
    assert not report["valid"]
    # Pydantic will catch missing fields in PlantSpecification
    errors = [e["location"] for e in report["errors"]]
    assert "components" in errors
    assert "properties" in errors

def test_rule2_invalid_component_ref():
    data = load_fixture("invalid_references.yaml")
    report = validate_spec(data)
    assert not report["valid"]
    error_msgs = [e["message"] for e in report["errors"]]
    assert any("Component 'UNDEFINED_COMP' used but not defined" in m for m in error_msgs)

def test_rule3_invalid_stream_connectivity():
    data = load_fixture("invalid_references.yaml")
    report = validate_spec(data)
    assert not report["valid"]
    error_msgs = [e["message"] for e in report["errors"]]
    assert any("Undefined input stream" in m for m in error_msgs)

def test_rule4_composition_sum():
    data = load_fixture("invalid_composition.yaml")
    report = validate_spec(data)
    assert not report["valid"]
    assert any("Composition sum is 0.95" in e["message"] for e in report["errors"])

def test_rule5_invalid_block_ref():
    data = load_fixture("invalid_references.yaml")
    report = validate_spec(data)
    assert not report["valid"]
    error_msgs = [e["message"] for e in report["errors"]]
    assert any("Block 'UNDEFINED-BLOCK' referenced but not defined" in m for m in error_msgs)

def test_rule6_invalid_units():
    data = load_fixture("invalid_units.yaml")
    report = validate_spec(data)
    assert not report["valid"]
    locations = [e["location"] for e in report["errors"]]
    assert "metadata.units.pressure" in locations
    assert "metadata.units.temperature" in locations
    assert "metadata.units.flow" in locations

def test_rule7_missing_required_fields():
    data = load_fixture("invalid_missing_fields.yaml")
    report = validate_spec(data)
    assert not report["valid"]
    locations = [e["location"] for e in report["errors"]]
    assert "streams.0.temperature" in locations
    assert "streams.0.pressure" in locations

def test_rule8_type_validation():
    data = load_fixture("invalid_types.yaml")
    report = validate_spec(data)
    assert not report["valid"]
    locations = [e["location"] for e in report["errors"]]
    assert "streams.0.temperature" in locations

def test_valid_spec_passes_all():
    data = load_fixture("valid_plant.yaml")
    report = validate_spec(data)
    assert report["valid"]
    assert len(report["errors"]) == 0

def test_chemistry_invalid_component_ref():
    data = load_fixture("invalid_chemistry.yaml")
    report = validate_spec(data)
    assert not report["valid"]
    # Check that the location path includes .stoichiometry
    locations = [e["location"] for e in report["errors"]]
    assert "chemistry[0].reactions[0].stoichiometry[0]" in locations

    error_msgs = [e["message"] for e in report["errors"]]
    assert any("Component 'UNDEFINED_COMP' used in reaction but not defined" in m for m in error_msgs)

def test_rule9_duplicate_names():
    data = load_fixture("duplicate_names.yaml")
    report = validate_spec(data)
    assert not report["valid"]

    locations = [e["location"] for e in report["errors"]]
    assert "components[1]" in locations
    assert "streams[1]" in locations
    assert "blocks[1]" in locations

    error_msgs = [e["message"] for e in report["errors"]]
    assert any("Duplicate component ID 'CH4' found" in m for m in error_msgs)
    assert any("Duplicate stream name 'S1' found" in m for m in error_msgs)
    assert any("Duplicate block name 'B1' found" in m for m in error_msgs)

def test_unknown_fields_validation():
    data = load_fixture("unknown_fields.yaml")
    report = validate_spec(data)
    assert not report["valid"]

    locations = [e["location"] for e in report["errors"]]
    # We expect errors for both 'metadata.unknown_metadata_field' and 'unknown_root_field'
    assert "metadata.unknown_metadata_field" in locations
    assert "unknown_root_field" in locations

    for error in report["errors"]:
        if error["location"] in ["metadata.unknown_metadata_field", "unknown_root_field"]:
            assert "Extra inputs are not permitted" in error["message"]


def test_requil_reactions_require_equilibrium_parameters():
    data = {
        "metadata": {"title": "Req Reactions", "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}},
        "components": [{"id": "A", "name": "A"}, {"id": "B", "name": "B"}],
        "properties": {"method": "IDEAL"},
        "flowsheet": [{"block": "R1", "inputs": ["S1"], "outputs": ["S2"]}],
        "streams": [
            {"name": "S1", "temperature": 25, "pressure": 1, "mass_flow": 1, "composition": {"A": 1.0}},
            {"name": "S2", "temperature": 25, "pressure": 1, "mole_flow": 1, "composition": {"B": 1.0}},
        ],
        "blocks": [{"name": "R1", "type": "REQUIL", "reactions": "RXN-SET1"}],
        "chemistry": [
            {
                "id": "SET1",
                "reactions": [
                    {
                        "id": 1,
                        "stoichiometry": [
                            {"component": "A", "coefficient": -1},
                            {"component": "B", "coefficient": 1},
                        ],
                    }
                ],
            }
        ],
        "reaction_sets": [{"id": "RXN-SET1", "block_type": "REQUIL", "reaction_ids": [1]}],
    }

    report = validate_spec(data)
    assert not report["valid"]
    locations = [e["location"] for e in report["errors"]]
    assert "chemistry[0].reactions[0].parameters" in locations


def test_rplug_kinetic_reaction_set_validates():
    data = {
        "metadata": {"title": "RPlug Kinetics", "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}},
        "components": [{"id": "CO", "name": "CO"}, {"id": "H2", "name": "H2"}, {"id": "CH3OH", "name": "MEOH"}],
        "properties": {"method": "RK-SOAVE"},
        "flowsheet": [{"block": "B-SYN", "inputs": ["R-IN"], "outputs": ["R-OUT"]}],
        "streams": [
            {"name": "R-IN", "temperature": 250, "pressure": 80, "mass_flow": 1, "composition": {"CO": 0.3, "H2": 0.7}},
            {"name": "R-OUT", "temperature": 250, "pressure": 80, "mass_flow": 1, "composition": {"CO": 0.2, "H2": 0.6, "CH3OH": 0.2}},
        ],
        "blocks": [{"name": "B-SYN", "type": "RPLUG", "reactions": "RXN-SET1"}],
        "chemistry": [
            {
                "id": "MEOH-KINETIC",
                "reactions": [
                    {
                        "id": 1,
                        "stoichiometry": [
                            {"component": "CO", "coefficient": -1},
                            {"component": "H2", "coefficient": -2},
                            {"component": "CH3OH", "coefficient": 1},
                        ],
                        "parameters": {
                            "reaction_type": "KINETIC",
                            "phase": "V",
                            "rate_basis": "MOLARITY",
                            "pre_exponential_factor": 1e-4,
                            "activation_energy": 60000,
                        },
                    }
                ],
            }
        ],
        "reaction_sets": [{"id": "RXN-SET1", "block_type": "POWERLAW", "reaction_ids": [1]}],
    }

    report = validate_spec(data)

    assert report["valid"], report["errors"]


def _lhhw_spec(adsorp_exponents: dict | None = None) -> dict:
    return {
        "metadata": {
            "title": "LHHW",
            "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"},
        },
        "components": [
            {"id": "CO2", "name": "CARBON-DIOXIDE"},
            {"id": "H2", "name": "HYDROGEN"},
            {"id": "CO", "name": "CARBON-MONOXIDE"},
            {"id": "H2O", "name": "WATER"},
        ],
        "properties": {"method": "SRK"},
        "flowsheet": [{"block": "B-SYN", "inputs": ["FEED"], "outputs": ["PROD"]}],
        "streams": [
            {"name": "FEED", "temperature": 220, "pressure": 50, "mass_flow": 1000,
             "composition": {"CO2": 0.25, "H2": 0.75}},
            {"name": "PROD", "temperature": 220, "pressure": 50, "mass_flow": 1000,
             "composition": {"CO2": 0.2, "H2": 0.6, "CO": 0.1, "H2O": 0.1}},
        ],
        "blocks": [
            {"name": "B-SYN", "type": "RPLUG",
             "parameters": {"TEMP": 220, "PRES": 50, "LENGTH": 8.0, "DIAM": 4.0, "NPOINT": 20},
             "reactions": "RXN-LHHW"},
        ],
        "chemistry": [
            {"id": "MEOH-LHHW", "reactions": [
                {"id": 1,
                 "stoichiometry": [
                     {"component": "CO2", "coefficient": -1},
                     {"component": "H2", "coefficient": -1},
                     {"component": "CO", "coefficient": 1},
                     {"component": "H2O", "coefficient": 1}],
                 "parameters": {
                     "reaction_type": "LHHW", "phase": "V", "name": "RWGS",
                     "kinetic_factor": {"pre_exp": 0.5, "act_energy": 20.0, "t_ref": 500.0},
                     "driving_force": {
                         "term1": {"exponents": {"CO2": 1.0}, "coeff": [0.0, 0.0]},
                         "term2": {"exponents": {"CO": 1.0, "H2O": 1.0, "H2": -1.0}, "coeff": [-4.0, 4000.0]}},
                     "adsorption": {
                         "power": 2.0,
                         "terms": [{"coeff": [0.0]}, {"coeff": [8.0, 0.0]}],
                         "exponents": adsorp_exponents if adsorp_exponents is not None else {"H2O": [0.0, 1.0]}}}},
            ]},
        ],
        "reaction_sets": [{"id": "RXN-LHHW", "block_type": "GENERAL", "reaction_ids": [1]}],
    }


def test_validate_accepts_well_formed_lhhw_spec():
    report = validate_spec(_lhhw_spec())
    assert report["valid"], report["errors"]


def test_validate_rejects_lhhw_adsorption_component_not_in_components():
    report = validate_spec(_lhhw_spec(adsorp_exponents={"ARGON": [0.0, 1.0]}))
    assert not report["valid"]
    messages = " ".join(e["message"] for e in report["errors"])
    assert "ARGON" in messages


def test_validate_rejects_mixed_lhhw_and_non_lhhw_set():
    spec = {
        "metadata": {"title": "Mix", "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}},
        "components": [
            {"id": "CO2", "name": "CARBON-DIOXIDE"}, {"id": "H2", "name": "HYDROGEN"},
            {"id": "CO", "name": "CARBON-MONOXIDE"}, {"id": "H2O", "name": "WATER"},
            {"id": "CH3OH", "name": "METHANOL"}],
        "properties": {"method": "SRK"},
        "flowsheet": [{"block": "B-SYN", "inputs": ["FEED"], "outputs": ["PROD"]}],
        "streams": [
            {"name": "FEED", "temperature": 220, "pressure": 50, "mass_flow": 1000,
             "composition": {"CO2": 0.25, "H2": 0.75}},
            {"name": "PROD", "temperature": 220, "pressure": 50, "mass_flow": 1000,
             "composition": {"CO2": 0.2, "H2": 0.5, "CO": 0.1, "H2O": 0.1, "CH3OH": 0.1}}],
        "blocks": [
            {"name": "B-SYN", "type": "RPLUG",
             "parameters": {"TEMP": 220, "PRES": 50, "LENGTH": 8.0, "DIAM": 4.0, "NPOINT": 20},
             "reactions": "RXN-MIX"}],
        "chemistry": [
            {"id": "MIX", "reactions": [
                {"id": 1, "stoichiometry": [
                    {"component": "CO2", "coefficient": -1}, {"component": "H2", "coefficient": -1},
                    {"component": "CO", "coefficient": 1}, {"component": "H2O", "coefficient": 1}],
                 "parameters": {
                     "reaction_type": "LHHW", "phase": "V", "name": "RWGS",
                     "kinetic_factor": {"pre_exp": 0.5, "act_energy": 20.0, "t_ref": 500.0},
                     "driving_force": {
                         "term1": {"exponents": {"CO2": 1.0}, "coeff": [0.0, 0.0]},
                         "term2": {"exponents": {"H2": -1.0}, "coeff": [-4.0, 4000.0]}},
                     "adsorption": {"power": 2.0, "terms": [{"coeff": [0.0]}, {"coeff": [8.0, 0.0]}],
                                    "exponents": {"H2O": [0.0, 1.0]}}}},
                {"id": 2, "stoichiometry": [
                    {"component": "CO2", "coefficient": -1}, {"component": "H2", "coefficient": -3},
                    {"component": "CH3OH", "coefficient": 1}, {"component": "H2O", "coefficient": 1}],
                 "parameters": {"reaction_type": "KINETIC", "phase": "V", "rate_basis": "MOLARITY",
                                "pre_exponential_factor": 1e-4, "activation_energy": 60000}},
            ]}],
        "reaction_sets": [{"id": "RXN-MIX", "block_type": "GENERAL", "reaction_ids": [1, 2]}],
    }
    report = validate_spec(spec)
    assert not report["valid"]
    assert any("mixes LHHW" in e["message"] for e in report["errors"])
