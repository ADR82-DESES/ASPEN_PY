import pytest
import os
import yaml
from aspen_automation.schema import validate_spec
from aspen_automation.parser import load_spec

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

def load_fixture(filename):
    filepath = os.path.join(FIXTURES_DIR, filename)
    with open(filepath, 'r') as f:
        return yaml.safe_load(f)

def test_valid_plant():
    spec = load_fixture("valid_plant.yaml")
    report = validate_spec(spec)
    assert report["valid"] is True
    assert len(report["errors"]) == 0


def test_schema_validate_spec_delegates_to_canonical_validator():
    from aspen_automation.validator import validate_spec as canonical_validate_spec

    spec = load_fixture("invalid_units.yaml")

    assert validate_spec(spec) == canonical_validate_spec(spec)

def test_methanol_plant_validates():
    spec = load_fixture("methanol_atr.yaml")
    report = validate_spec(spec)
    if not report["valid"]:
        print(f"\nVALIDATION ERRORS: {report['errors']}")
    assert report["valid"] is True
    assert len(report["errors"]) == 0

def test_missing_metadata():
    spec = load_fixture("valid_plant.yaml")
    del spec["metadata"]
    report = validate_spec(spec)
    assert report["valid"] is False
    assert any(e["location"] == "metadata" and "Field required" in e["message"] for e in report["errors"])

def test_missing_components_section():
    spec = load_fixture("invalid_missing_section.yaml")
    report = validate_spec(spec)
    assert report["valid"] is False
    assert any(e["location"] == "components" and "Field required" in e["message"] for e in report["errors"])

def test_invalid_units():
    spec = load_fixture("invalid_units.yaml")
    report = validate_spec(spec)
    assert report["valid"] is False
    assert any("Invalid unit 'invalid_pressure' for pressure" in e["message"] for e in report["errors"])

def test_invalid_component_reference():
    spec = load_fixture("invalid_component_ref.yaml")
    report = validate_spec(spec)
    assert report["valid"] is False
    assert any("Component 'UNKNOWN_COMP' used but not defined" in e["message"] for e in report["errors"])

def test_invalid_stream_reference():
    spec = load_fixture("invalid_stream_ref.yaml")
    report = validate_spec(spec)
    assert report["valid"] is False
    assert any("Undefined input stream 'S_UNKNOWN'" in e["message"] for e in report["errors"])

def test_invalid_block_reference():
    spec = load_fixture("invalid_block_ref.yaml")
    report = validate_spec(spec)
    assert report["valid"] is False
    assert any("Block 'B_UNKNOWN' referenced but not defined" in e["message"] for e in report["errors"])

def test_invalid_composition_sum():
    spec = load_fixture("invalid_composition_sum.yaml")
    report = validate_spec(spec)
    assert report["valid"] is False
    assert any("expected 1.0" in e["message"] for e in report["errors"])

def test_missing_required_fields():
    spec = load_fixture("invalid_missing_field.yaml")
    report = validate_spec(spec)
    assert report["valid"] is False
    assert any(e["location"] == "streams.0.temperature" and "Field required" in e["message"] for e in report["errors"])

def test_invalid_types():
    spec = load_fixture("invalid_types.yaml")
    report = validate_spec(spec)
    assert report["valid"] is False
    assert any(e["location"] == "streams.0.temperature" and "valid number" in e["message"] for e in report["errors"])

def test_empty_spec():
    report = validate_spec({})
    assert report["valid"] is False
    assert len(report["errors"]) >= 6 # Missing all 6 required sections


def test_process_defaults_model_accepts_all_fields():
    """ProcessDefaults Pydantic model must exist and accept all three fields."""
    from aspen_automation.schema import ProcessDefaults
    pd_model = ProcessDefaults(
        purity_expression="CH3OH wt% in MEOH-PRO",
        product_stream="MEOH-PRO",
        convergence_block="B-ATR",
    )
    assert pd_model.purity_expression == "CH3OH wt% in MEOH-PRO"
    assert pd_model.product_stream == "MEOH-PRO"
    assert pd_model.convergence_block == "B-ATR"


def test_process_defaults_model_accepts_partial_fields():
    """ProcessDefaults fields are all optional; partial construction must not raise."""
    from aspen_automation.schema import ProcessDefaults
    pd_model = ProcessDefaults(purity_expression="NH3 wt% in NH3-PROD")
    assert pd_model.purity_expression == "NH3 wt% in NH3-PROD"
    assert pd_model.product_stream is None
    assert pd_model.convergence_block is None


def test_plant_specification_accepts_process_defaults():
    """PlantSpecification must accept an optional process_defaults section."""
    from aspen_automation.schema import PlantSpecification
    spec_dict = load_fixture("methanol_atr.yaml")
    spec_dict["process_defaults"] = {
        "purity_expression": "CH3OH wt% in MEOH-PRO",
        "product_stream": "MEOH-PRO",
        "convergence_block": "B-ATR",
    }
    report = validate_spec(spec_dict)
    assert report["valid"] is True
    ps = PlantSpecification.model_validate(spec_dict)
    assert ps.process_defaults is not None
    assert ps.process_defaults.product_stream == "MEOH-PRO"
    assert ps.process_defaults.convergence_block == "B-ATR"


def test_plant_specification_accepts_kinetic_model_metadata():
    from aspen_automation.schema import PlantSpecification
    spec_dict = load_fixture("methanol_atr.yaml")
    spec_dict["kinetic_models"] = [
        {
            "id": "VBF96_SCREENING",
            "implementation": "POWERLAW screening surrogate",
            "primary_reference": "Vanden Bussche and Froment 1996",
        }
    ]
    report = validate_spec(spec_dict)
    assert report["valid"] is True
    ps = PlantSpecification.model_validate(spec_dict)
    assert ps.kinetic_models is not None
    assert ps.kinetic_models[0]["id"] == "VBF96_SCREENING"


def test_schema_accepts_source_tagged_nrtl_binary_parameters():
    from aspen_automation.schema import PlantSpecification

    spec_dict = load_fixture("methanol_atr.yaml")
    spec_dict["properties"] = {
        "method": "NRTL",
        "binary_parameters": [
            {
                "components": ["CH3OH", "H2O"],
                "model": "NRTL",
                "source_type": "aspen_databank",
                "databanks": ["APV140 VLE-IG", "APV140 VLE-LIT"],
                "basis": "Aspen Plus V14 NRTL property databank interaction parameters",
                "provenance": {"source": "Aspen Plus V14 property databanks"},
            }
        ],
    }

    report = validate_spec(spec_dict)

    assert report["valid"] is True
    ps = PlantSpecification.model_validate(spec_dict)
    assert ps.properties.binary_parameters[0].components == ["CH3OH", "H2O"]


def test_schema_rejects_malformed_nrtl_binary_parameters():
    spec_dict = load_fixture("methanol_atr.yaml")
    spec_dict["properties"] = {
        "method": "NRTL",
        "binary_parameters": [
            {
                "components": ["CH3OH", "CH3OH"],
                "source_type": "explicit",
                "values": {"unsupported": 1.0},
            }
        ],
    }

    report = validate_spec(spec_dict)
    messages = [error["message"] for error in report["errors"]]

    assert report["valid"] is False
    assert any("must be distinct" in message for message in messages)
    assert any(error["location"] == "properties.binary_parameters.0.provenance" for error in report["errors"])
    assert any("unsupported NRTL binary parameter field" in message for message in messages)


def _minimal_column_spec():
    return {
        "metadata": {
            "title": "Minimal Column",
            "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"},
        },
        "components": [
            {"id": "A", "name": "A"},
            {"id": "B", "name": "B"},
        ],
        "properties": {"method": "NRTL"},
        "flowsheet": [
            {"block": "V1", "inputs": ["FEED"], "outputs": ["FEED-LP"]},
            {"block": "COL1", "inputs": ["FEED-LP"], "outputs": ["DIST", "BOT"]},
        ],
        "streams": [
            {"name": "FEED", "temperature": 25, "pressure": 10, "mass_flow": 100, "composition": {"A": 0.5, "B": 0.5}},
            {"name": "FEED-LP", "temperature": 25, "pressure": 1.8, "mass_flow": 100, "composition": {"A": 0.5, "B": 0.5}},
            {"name": "DIST", "temperature": 25, "pressure": 1.5, "mass_flow": 50, "composition": {"A": 0.99, "B": 0.01}},
            {"name": "BOT", "temperature": 25, "pressure": 2.08, "mass_flow": 50, "composition": {"A": 0.01, "B": 0.99}},
        ],
        "blocks": [
            {"name": "V1", "type": "VALVE", "parameters": {"P-OUT": 1.8}},
            {
                "name": "COL1",
                "type": "RADFRAC",
                "radfrac": {
                    "n_stages": 30,
                    "feed_stage": 16,
                    "condenser": "TOTAL",
                    "reboiler": "KETTLE",
                    "top_pressure": 1.5,
                    "pressure_drop_per_stage": 0.02,
                    "reflux_ratio": 2.0,
                    "bottoms_rate": 50.0,
                    "rate_basis": "MASS",
                    "max_outer_iterations": 50,
                },
            },
        ],
        "targets": {
            "production_rate_tpd": 1.0,
            "product_conditions": [
                {"stream": "DIST", "pressure": 1.5, "pressure_tolerance": 0.05}
            ],
            "component_loss_limits": [
                {
                    "stream": "DIST",
                    "component": "A",
                    "max_tpd": 0.1,
                    "basis": "mass",
                    "baseline_tpd": 1.0,
                }
            ],
        },
    }


def test_schema_accepts_complete_valve_and_radfrac_blocks():
    report = validate_spec(_minimal_column_spec())
    assert report["valid"] is True


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda spec: spec["blocks"][1].pop("radfrac"), "RADFRAC"),
        (lambda spec: spec["blocks"][1]["radfrac"].update({"feed_stage": 31}), "feed_stage"),
        (lambda spec: spec["blocks"][1]["radfrac"].update({"pressure_drop_per_stage": -0.01}), "pressure_drop"),
        (lambda spec: spec["blocks"][1]["radfrac"].update({"condenser": "UNSUPPORTED"}), "condenser"),
        (lambda spec: spec["blocks"][1]["radfrac"].update({"bottoms_rate": -1}), "bottoms_rate"),
        (lambda spec: spec["flowsheet"][1].update({"outputs": ["DIST"]}), "two liquid"),
        (lambda spec: spec["blocks"][0]["parameters"].update({"P-OUT": -1}), "P-OUT"),
    ],
)
def test_schema_rejects_invalid_valve_and_radfrac_payloads(mutate, expected):
    spec = _minimal_column_spec()
    mutate(spec)

    report = validate_spec(spec)
    messages = " ".join(error["message"] for error in report["errors"])

    assert report["valid"] is False
    assert expected in messages


def test_schema_rejects_malformed_product_conditions():
    spec = _minimal_column_spec()
    spec["targets"]["product_conditions"] = [
        {"stream": "MISSING", "pressure": 1.5, "pressure_tolerance": -0.1}
    ]

    report = validate_spec(spec)
    messages = " ".join(error["message"] for error in report["errors"])

    assert report["valid"] is False
    assert "pressure_tolerance" in messages


def test_schema_rejects_malformed_component_loss_limits():
    spec = _minimal_column_spec()
    spec["targets"]["component_loss_limits"] = [
        {
            "stream": "MISSING",
            "component": "MISSING",
            "max_kg_hr": -1.0,
            "max_tpd": 1.0,
            "basis": "mole",
            "baseline_kg_hr": 1.0,
            "baseline_tpd": 1.0,
        }
    ]

    report = validate_spec(spec)
    messages = " ".join(error["message"] for error in report["errors"])

    assert report["valid"] is False
    assert "basis: mass" in messages
