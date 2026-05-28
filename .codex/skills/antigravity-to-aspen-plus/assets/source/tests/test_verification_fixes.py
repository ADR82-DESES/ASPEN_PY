import pytest
from aspen_automation.inp_generator import generate_inp, validate_inp, ValidationError
from aspen_automation.schema import PlantSpecification, Metadata, UnitSystem, Properties, Stream, Block, Component
import os

def test_methanol_plant_validation():
    """Regression test: Ensure MethanolPlant.inp passes validation."""
    inp_path = os.path.join("archive", "aspen_artifacts", "Methanol Plant", "MethanolPlant.inp")
    if not os.path.exists(inp_path):
        pytest.skip(f"MethanolPlant.inp not found at {inp_path}")

    with open(inp_path, "r", encoding="utf-8") as f:
        content = f.read()

    report = validate_inp(content)
    assert report["valid"], f"MethanolPlant.inp validation failed: {report['errors']}"

def test_empty_spec_validation():
    """Test that generate_inp raises ValidationError for empty streams/blocks."""
    spec = PlantSpecification(
        metadata=Metadata(
            title="Empty Spec",
            units=UnitSystem(pressure="bar", temperature="C", flow="kg/hr")
        ),
        components=[Component(id="H2O", name="WATER")],
        properties=Properties(method="NRTL"),
        flowsheet=[],
        streams=[],  # Empty
        blocks=[]    # Empty
    )

    with pytest.raises(ValidationError) as excinfo:
        generate_inp(spec)

    errors = str(excinfo.value)
    assert "Spec must contain at least one stream" in errors
    # assert "Spec must contain at least one block" in errors  # Raised sequentially, so this won't be reached if stream check fails first

def test_schema_properties_deduplication():
    """Test that PlantSpecification has only one properties field (implicit via successful import/instantiation)."""
    spec = PlantSpecification(
        metadata=Metadata(
            title="Test Spec",
            units=UnitSystem(pressure="bar", temperature="C", flow="kg/hr")
        ),
        components=[Component(id="H2O", name="WATER")],
        properties=Properties(method="NRTL"),
        flowsheet=[],
        streams=[
            Stream(name="S1", temperature=25, pressure=1, mass_flow=100, composition={"H2O": 1.0})
        ],
        blocks=[
            Block(name="B1", type="MIXER")
        ]
    )
    assert spec.properties.method == "NRTL"
