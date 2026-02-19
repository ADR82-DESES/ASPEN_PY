import pytest
from aspen_automation.schema import PlantSpecification, Stream, Component, Metadata, UnitSystem, Properties
from pydantic import ValidationError

def test_valid_stream():
    s = Stream(
        name="FEED",
        temperature=25.0,
        pressure=1.0,
        mass_flow=100.0,
        composition={"H2O": 1.0}
    )
    assert s.name == "FEED"
    assert s.composition["H2O"] == 1.0

def test_invalid_composition_sum():
    with pytest.raises(ValidationError) as excinfo:
        Stream(
            name="FEED",
            temperature=25.0,
            pressure=1.0,
            mass_flow=100.0,
            composition={"H2O": 0.5, "CH4": 0.4} # Sum is 0.9
        )
    assert "Composition sum is 0.9" in str(excinfo.value)

def test_missing_flow():
    with pytest.raises(ValidationError) as excinfo:
        Stream(
            name="FEED",
            temperature=25.0,
            pressure=1.0,
            composition={"H2O": 1.0}
            # missing volume/mass/mole flow
        )
    assert "Either mass_flow or mole_flow must be provided" in str(excinfo.value)

def test_plant_spec_minimal():
    metadata = Metadata(
        title="Test",
        units=UnitSystem(pressure="bar", temperature="C", flow="kg/hr")
    )
    props = Properties(method="IDEAL")
    spec = PlantSpecification(
        metadata=metadata,
        components=[],
        properties=props,
        flowsheet=[],
        streams=[],
        blocks=[]
    )
    assert spec.metadata.title == "Test"

def test_forbid_extra_fields():
    with pytest.raises(ValidationError) as excinfo:
        Component(id="C1", name="Comp1", extra_field="not_allowed")
    assert "extra_field" in str(excinfo.value)
    assert "Extra inputs are not permitted" in str(excinfo.value)
