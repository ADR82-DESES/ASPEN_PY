
import pytest
from aspen_automation.inp_generator import generate_inp
from aspen_automation.schema import PlantSpecification

def test_inp_eng_flow_units_mixed():
    # Case: Flow is English (LB/HR), but Temp/Pres are Metric (C/BAR).
    # Expected: IN-UNITS ENG ...
    spec = PlantSpecification(**{
        "metadata": {
            "title": "Mixed Units Test",
            "units": {"pressure": "bar", "temperature": "C", "flow": "lb/hr"}
        },
        "components": [{"id": "H2O", "name": "WATER"}],
        "properties": {"method": "IDEAL"},
        "flowsheet": [],
        "streams": [],
        "blocks": []
    })
    inp = generate_inp(spec)
    
    # We expect ENG because flow is LB/HR
    assert "IN-UNITS ENG" in inp, f"Expected IN-UNITS ENG, but got: {inp}"
    assert "FLOW='LB/HR'" in inp

def test_inp_eng_flow_units_lbmol_mixed():
    # Case: Flow is English (LBMOL/HR), but Temp/Pres are Metric (C/BAR).
    # Expected: IN-UNITS ENG ...
    spec = PlantSpecification(**{
        "metadata": {
            "title": "Mixed Units Test 2",
            "units": {"pressure": "bar", "temperature": "C", "flow": "lbmol/hr"}
        },
        "components": [{"id": "H2O", "name": "WATER"}],
        "properties": {"method": "IDEAL"},
        "flowsheet": [],
        "streams": [],
        "blocks": []
    })
    inp = generate_inp(spec)
    
    # We expect ENG because flow is LBMOL/HR
    assert "IN-UNITS ENG" in inp, f"Expected IN-UNITS ENG, but got: {inp}"
    assert "FLOW='LBMOL/HR'" in inp
