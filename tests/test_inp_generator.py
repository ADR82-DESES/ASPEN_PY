import os
import re
import shutil
import uuid
import pytest

from aspen_automation.exceptions import ValidationError
from aspen_automation.inp_generator import generate_inp, validate_inp
from aspen_automation.schema import PlantSpecification
from aspen_automation.parser import load_spec

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
REFERENCE_DIR = os.path.join(os.path.dirname(__file__), "..", "Methanol Plant")


@pytest.fixture
def valid_spec_data():
    path = os.path.join(FIXTURE_DIR, "valid_plant.yaml")
    return load_spec(path)


@pytest.fixture
def minimal_spec():
    return PlantSpecification(**{
        "metadata": {
            "title": "Minimal Plant",
            "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}
        },
        "components": [
            {"id": "H2O", "name": "WATER", "formula": "H2O"}
        ],
        "properties": {"method": "STEAM-TA"},
        "flowsheet": [
            {"block": "B1", "inputs": ["S1"], "outputs": ["S2"]}
        ],
        "streams": [
            {
                "name": "S1",
                "temperature": 100,
                "pressure": 1,
                "mass_flow": 1000,
                "composition": {"H2O": 1.0}
            },
            {
                "name": "S2",
                "temperature": 150,
                "pressure": 1,
                "mass_flow": 1000,
                "composition": {"H2O": 1.0}
            }
        ],
        "blocks": [
            {"name": "B1", "type": "HEATER", "parameters": {"temp": 150, "pres": 0}}
        ]
    })


def test_generate_minimal_inp(minimal_spec):
    inp = generate_inp(minimal_spec)
    report = validate_inp(inp)
    assert report["valid"]

    assert "TITLE 'Minimal Plant'" in inp
    assert "IN-UNITS MET PRESSURE=BAR TEMPERATURE=C FLOW='KG/HR'" in inp
    assert "DEF-STREAMS CONVEN ALL" in inp
    assert "COMPONENTS" in inp
    assert "H2O WATER H2O /" in inp
    assert "PROPERTIES STEAM-TA" in inp
    assert "FLOWSHEET" in inp
    assert "BLOCK B1 IN=S1 OUT=S2" in inp
    assert "STREAM S1" in inp
    assert "SUBSTREAM MIXED TEMP=100.0 PRES=1.0 &" in inp
    assert "MASS-FLOW=1000.0" in inp
    assert "BLOCK B1 HEATER" in inp
    assert "TEMP=150.0" in inp


def test_generate_complex_inp():
    path = os.path.join(FIXTURE_DIR, "methanol_atr.yaml")
    spec = load_spec(path)
    inp = generate_inp(spec)
    report = validate_inp(inp)
    assert report["valid"]

    assert "TITLE 'Methanol Production Plant'" in inp
    assert "COMPONENTS" in inp
    assert "CH4 METHANE" in inp
    assert "PROPERTIES RK-SOAVE" in inp
    assert "FLOWSHEET" in inp
    assert "BLOCK MIX-FEED" in inp
    assert "STREAM NAT-GAS" in inp
    assert "BLOCK REFORMER" in inp


def test_methanol_template_stream_compositions_use_canonical_rows():
    path = os.path.join(os.path.dirname(__file__), "..", "templates", "methanol_plant_atr.yaml")
    spec = load_spec(path)
    inp = generate_inp(spec)
    report = validate_inp(inp)

    assert report["valid"]
    assert not any(
        re.match(r"\s+(?:MOLE|MASS)-FRAC\s+\S+\s+[-+0-9.]", line)
        for line in inp.splitlines()
    )
    assert "    MOLE-FRAC\n        O2 0.995 / &\n        N2 0.005 /" in inp


def test_validate_inp_rejects_inline_composition_rows_without_terminators():
    inp = """TITLE 'Bad Composition'
IN-UNITS MET PRESSURE=BAR TEMPERATURE=C FLOW='KG/HR'
DEF-STREAMS CONVEN ALL
DATABANKS 'APV140 PURE32'
PROP-SOURCES 'APV140 PURE32'
COMPONENTS
    H2O WATER /
    ET-OH ETHANOL /
PROPERTIES NRTL
FLOWSHEETING-OPTIONS
    MASS-BAL=YES ENERGY-BAL=YES
FLOWSHEET
    BLOCK B1 IN=S1 OUT=S2
STREAM S1
    SUBSTREAM MIXED TEMP=25.0 PRES=1.0 &
        MASS-FLOW=100.0
    MOLE-FRAC H2O 0.5
    MOLE-FRAC ET-OH 0.5
STREAM S2
    SUBSTREAM MIXED TEMP=25.0 PRES=1.0 &
        MASS-FLOW=100.0
    MOLE-FRAC
        H2O 0.5 / &
        ET-OH 0.5 /
BLOCK B1 MIXER
"""

    report = validate_inp(inp)

    assert not report["valid"]
    assert any("Composition line missing '/' terminator" in e["message"] for e in report["errors"])


def test_inp_unit_conversion():
    spec = PlantSpecification(**{
        "metadata": {
            "title": "Unit Test",
            "units": {"pressure": "PSI", "temperature": "f", "flow": "Lb/Hr"}
        },
        "components": [{"id": "H2O", "name": "WATER"}],
        "properties": {"method": "IDEAL"},
        "flowsheet": [{"block": "B1", "inputs": ["S1"], "outputs": ["S2"]}],
        "streams": [
            {"name": "S1", "temperature": 25, "pressure": 1, "mass_flow": 1, "composition": {"H2O": 1.0}},
            {"name": "S2", "temperature": 25, "pressure": 1, "mole_flow": 1, "composition": {"H2O": 1.0}}
        ],
        "blocks": [{"name": "B1", "type": "MIXER"}]
    })
    inp = generate_inp(spec)
    assert "IN-UNITS ENG" in inp
    assert "PRESSURE=PSI" in inp
    assert "TEMPERATURE=F" in inp
    assert "FLOW='LB/HR'" in inp


def test_inp_si_units():
    spec = PlantSpecification(**{
        "metadata": {
            "title": "SI Test",
            "units": {"pressure": "kPa", "temperature": "K", "flow": "kg/hr"}
        },
        "components": [{"id": "H2O", "name": "WATER"}],
        "properties": {"method": "IDEAL"},
        "flowsheet": [{"block": "B1", "inputs": ["S1"], "outputs": ["S2"]}],
        "streams": [
            {"name": "S1", "temperature": 298.15, "pressure": 1, "mass_flow": 1, "composition": {"H2O": 1.0}},
            {"name": "S2", "temperature": 298.15, "pressure": 1, "mole_flow": 1, "composition": {"H2O": 1.0}}
        ],
        "blocks": [{"name": "B1", "type": "MIXER"}]
    })
    inp = generate_inp(spec)
    assert "IN-UNITS SI" in inp
    assert "PRESSURE=KPA" in inp
    assert "TEMPERATURE=K" in inp
    assert "FLOW='KG/HR'" in inp


def test_inp_chemistry_section():
    spec = PlantSpecification(**{
        "metadata": {
            "title": "Chem Test",
            "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}
        },
        "components": [
            {"id": "A", "name": "A"},
            {"id": "B", "name": "B"}
        ],
        "properties": {"method": "IDEAL"},
        "flowsheet": [{"block": "B1", "inputs": ["S1"], "outputs": ["S2"]}],
        "streams": [
            {"name": "S1", "temperature": 25, "pressure": 1, "mass_flow": 1, "composition": {"A": 1.0}},
            {"name": "S2", "temperature": 25, "pressure": 1, "mole_flow": 1, "composition": {"A": 1.0}}
        ],
        "blocks": [{"name": "B1", "type": "MIXER"}],
        "chemistry": [
            {
                "id": "GLOBAL",
                "reactions": [
                    {
                        "id": 1,
                        "stoichiometry": [
                            {"component": "A", "coefficient": -1},
                            {"component": "B", "coefficient": 1}
                        ]
                    }
                ]
            }
        ]
    })
    inp = generate_inp(spec)
    assert "CHEMISTRY GLOBAL" in inp
    assert "STOIC 1 &" in inp
    assert "A -1.0 / &" in inp
    assert "B 1.0 /" in inp


def test_generate_inp_file_output(minimal_spec):
    base_dir = os.path.abspath("test_results")
    os.makedirs(base_dir, exist_ok=True)
    tmpdir = os.path.join(base_dir, f"inp_generator_{uuid.uuid4().hex}")
    os.makedirs(tmpdir, exist_ok=False)

    try:
        output_path = os.path.join(tmpdir, "test.inp")
        generate_inp(minimal_spec, output_path=str(output_path))
        assert os.path.exists(output_path)
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    assert "TITLE 'Minimal Plant'" in content


def test_structure_comparison_with_baseline(valid_spec_data):
    """
    Compare generated structure with keywords found in MethanolPlant.inp.
    Manual verification in Aspen Plus is still required.
    """
    inp = generate_inp(valid_spec_data)
    baseline_path = os.path.join(REFERENCE_DIR, "MethanolPlant.inp")
    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline_content = f.read()

    baseline_keywords = [
        "TITLE",
        "IN-UNITS",
        "DEF-STREAMS",
        "DATABANKS",
        "PROP-SOURCES",
        "COMPONENTS",
        "PROPERTIES",
        "FLOWSHEET",
        "BLOCK",
        "STREAM",
        "SUBSTREAM",
    ]

    for kw in baseline_keywords:
        assert kw in baseline_content
        assert kw in inp


def test_compare_with_golden_minimal(minimal_spec):
    """
    Exact (normalized) comparison with a golden reference.
    """
    inp = generate_inp(minimal_spec)
    golden_path = os.path.join(FIXTURE_DIR, "golden_minimal.inp")
    with open(golden_path, "r", encoding="utf-8") as f:
        golden_content = f.read().strip()

    assert inp.strip().replace("\r\n", "\n") == golden_content.replace("\r\n", "\n")


def test_format_validation_continuation_and_quotes(minimal_spec):
    inp = generate_inp(minimal_spec)
    assert "DATABANKS 'APV140 PURE32'" in inp
    assert " / &" in inp
    assert "PROP-SOURCES 'APV140 PURE32'" in inp


def test_format_validation_terminators_and_indentation(minimal_spec):
    inp = generate_inp(minimal_spec)
    assert "    H2O WATER H2O /" in inp
    assert "    BLOCK B1 IN=S1 OUT=S2" in inp
    assert "        H2O 1.0 /" in inp


def test_flowsheet_multiple_inputs_outputs():
    spec = PlantSpecification(**{
        "metadata": {
            "title": "Flow Test",
            "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}
        },
        "components": [{"id": "A", "name": "A"}],
        "properties": {"method": "IDEAL"},
        "flowsheet": [
            {"block": "B1", "inputs": ["S1", "S2", "S3"], "outputs": ["S4", "S5"]}
        ],
        "streams": [
            {"name": "S1", "temperature": 10, "pressure": 1, "mass_flow": 1, "composition": {"A": 1.0}},
            {"name": "S2", "temperature": 10, "pressure": 1, "mass_flow": 1, "composition": {"A": 1.0}},
            {"name": "S3", "temperature": 10, "pressure": 1, "mass_flow": 1, "composition": {"A": 1.0}},
            {"name": "S4", "temperature": 10, "pressure": 1, "mass_flow": 1, "composition": {"A": 1.0}},
            {"name": "S5", "temperature": 10, "pressure": 1, "mass_flow": 1, "composition": {"A": 1.0}},
        ],
        "blocks": [{"name": "B1", "type": "MIXER"}]
    })

    inp = generate_inp(spec)
    assert "BLOCK B1 IN=S1 S2 S3 OUT=S4 S5" in inp


def test_stream_mass_and_mole_basis():
    spec = PlantSpecification(**{
        "metadata": {
            "title": "Stream Basis",
            "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}
        },
        "components": [{"id": "A", "name": "A"}],
        "properties": {"method": "IDEAL"},
        "flowsheet": [{"block": "B1", "inputs": ["S1"], "outputs": ["S2"]}],
        "streams": [
            {"name": "S1", "temperature": 10, "pressure": 1, "mass_flow": 1, "composition": {"A": 1.0}},
            {"name": "S2", "temperature": 10, "pressure": 1, "mole_flow": 2, "composition": {"A": 1.0}},
        ],
        "blocks": [{"name": "B1", "type": "MIXER"}]
    })

    inp = generate_inp(spec)
    assert inp.count("MOLE-FRAC") == 2
    assert "MOLE-FRAC" in inp


def test_block_parameter_types():
    spec = PlantSpecification(**{
        "metadata": {
            "title": "Param Types",
            "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}
        },
        "components": [{"id": "A", "name": "A"}],
        "properties": {"method": "IDEAL"},
        "properties": {"method": "IDEAL"},
        "flowsheet": [{"block": "B1", "inputs": ["S1"], "outputs": ["S2"]}],
        "streams": [
            {"name": "S1", "temperature": 25, "pressure": 1, "mass_flow": 1, "composition": {"A": 1.0}},
            {"name": "S2", "temperature": 25, "pressure": 1, "mole_flow": 1, "composition": {"A": 1.0}}
        ],
        "blocks": [
            {"name": "B1", "type": "HEATER", "parameters": {"temp": 250, "mode": "AUTO"}}
        ]
    })

    inp = generate_inp(spec)
    assert "PARAM" in inp
    assert "TEMP=250.0" in inp
    assert "MODE=AUTO" in inp


def test_chemistry_multiple_reactions():
    spec = PlantSpecification(**{
        "metadata": {
            "title": "Chem Multi",
            "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}
        },
        "components": [
            {"id": "A", "name": "A"},
            {"id": "B", "name": "B"},
            {"id": "C", "name": "C"},
        ],
        "properties": {"method": "IDEAL"},
        "flowsheet": [{"block": "B1", "inputs": ["S1"], "outputs": ["S2"]}],
        "streams": [
            {"name": "S1", "temperature": 25, "pressure": 1, "mass_flow": 100, "composition": {"A": 1.0}},
            {"name": "S2", "temperature": 25, "pressure": 1, "mole_flow": 100, "composition": {"A": 1.0}}
        ],
        "blocks": [{"name": "B1", "type": "MIXER"}],
        "chemistry": [
            {
                "id": "SET1",
                "reactions": [
                    {"id": 1, "stoichiometry": [{"component": "A", "coefficient": -1}, {"component": "B", "coefficient": 1}]},
                    {"id": 2, "stoichiometry": [{"component": "B", "coefficient": -1}, {"component": "C", "coefficient": 1}]},
                ]
            }
        ]
    })

    inp = generate_inp(spec)
    assert "STOIC 1 &" in inp
    assert "STOIC 2 &" in inp


def test_reactions_section_and_block_link():
    spec = PlantSpecification(**{
        "metadata": {
            "title": "Reaction Link",
            "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}
        },
        "components": [
            {"id": "A", "name": "A"},
            {"id": "B", "name": "B"}
        ],
        "properties": {"method": "IDEAL"},
        "flowsheet": [{"block": "R1", "inputs": ["S1"], "outputs": ["S2"]}],
        "streams": [
            {"name": "S1", "temperature": 25, "pressure": 1, "mass_flow": 100, "composition": {"A": 1.0}},
            {"name": "S2", "temperature": 25, "pressure": 1, "mole_flow": 100, "composition": {"A": 1.0}}
        ],
        "blocks": [
            {"name": "R1", "type": "REQUIL", "reactions": "RXN-SET1"}
        ],
        "chemistry": [
            {
                "id": "SET1",
                "reactions": [
                    {
                        "id": 1,
                        "stoichiometry": [{"component": "A", "coefficient": -1}, {"component": "B", "coefficient": 1}],
                        "parameters": {
                            "reaction_type": "EQUIL",
                            "phase": "V",
                            "equilibrium_form": "LNK-1/T",
                            "equilibrium_basis": "FUGACITY",
                            "equilibrium_constants": [1.0, -1000.0, 0.0, 0.0]
                        }
                    }
                ]
            }
        ],
        "reaction_sets": [
            {"id": "RXN-SET1", "block_type": "REQUIL", "reaction_ids": [1]}
        ]
    })

    inp = generate_inp(spec)
    assert "REACTIONS RXN-SET1 REQUIL" in inp
    assert "REAC-DATA 1" in inp
    assert "REAC-DATA 1 EQUIL" not in inp
    assert "K-STOIC 1 1.0 -1000.0 0.0 0.0" not in inp
    assert "BLOCK R1 REQUIL" in inp
    assert "REACTIONS RXN-SET1" in inp


def test_fsplit_and_sep_blocks():
    spec = PlantSpecification(**{
        "metadata": {
            "title": "Split Test",
            "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}
        },
        "components": [
            {"id": "A", "name": "A"},
            {"id": "B", "name": "B"}
        ],
        "properties": {"method": "IDEAL"},
        "flowsheet": [],
        "streams": [
            {"name": "RECYCLE", "temperature": 10, "pressure": 1, "mass_flow": 1, "composition": {"A": 1.0}},
            {"name": "PURGE", "temperature": 10, "pressure": 1, "mass_flow": 1, "composition": {"A": 1.0}},
            {"name": "PROD", "temperature": 10, "pressure": 1, "mass_flow": 1, "composition": {"A": 0.5, "B": 0.5}},
        ],
        "blocks": [
            {
                "name": "SPLIT1",
                "type": "FSPLIT",
                "split_fractions": [
                    {"stream": "RECYCLE", "fraction": 0.9},
                    {"stream": "PURGE", "fraction": 0.1}
                ]
            },
            {
                "name": "SEP1",
                "type": "SEP",
                "sep_fractions": [
                    {"stream": "PROD", "substream": "MIXED", "component": "A", "fraction": 0.99},
                    {"stream": "PROD", "substream": "MIXED", "component": "B", "fraction": 0.01}
                ]
            }
        ]
    })

    inp = generate_inp(spec)
    assert "BLOCK SPLIT1 FSPLIT" in inp
    assert "FRAC RECYCLE 0.9" in inp
    assert "BLOCK SEP1 SEP" in inp
    assert "BLOCK SEP1 SEP\n    PARAM\n    FRAC STRM=PROD" in inp
    assert "FRAC STRM=PROD SUBSTRM=MIXED COMP=A FRAC=0.99" in inp
    assert inp.endswith("\n")


def test_compressor_efficiency_uses_aspen_eff_keyword():
    spec = PlantSpecification(**{
        "metadata": {
            "title": "Compressor",
            "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}
        },
        "components": [{"id": "A", "name": "A"}],
        "properties": {"method": "NRTL"},
        "flowsheet": [{"block": "C1", "inputs": ["FEED"], "outputs": ["PROD"]}],
        "streams": [
            {"name": "FEED", "temperature": 25, "pressure": 1, "mass_flow": 100, "composition": {"A": 1.0}},
            {"name": "PROD", "temperature": 25, "pressure": 5, "mass_flow": 100, "composition": {"A": 1.0}},
        ],
        "blocks": [{"name": "C1", "type": "COMPR", "parameters": {"PRES": 5, "EFF": 0.85}}],
    })

    inp = generate_inp(spec)

    assert "        EFF=0.85" in inp
    assert "SEFF=0.85" not in inp


def test_generate_inp_rejects_unsupported_radfrac_until_emitter_exists():
    spec = PlantSpecification(**{
        "metadata": {
            "title": "Unsupported Column",
            "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}
        },
        "components": [{"id": "A", "name": "A"}],
        "properties": {"method": "NRTL"},
        "flowsheet": [{"block": "COL1", "inputs": ["FEED"], "outputs": ["DIST", "BOT"]}],
        "streams": [
            {"name": "FEED", "temperature": 25, "pressure": 1, "mass_flow": 100, "composition": {"A": 1.0}},
            {"name": "DIST", "temperature": 25, "pressure": 1, "mass_flow": 50, "composition": {"A": 1.0}},
            {"name": "BOT", "temperature": 25, "pressure": 1, "mass_flow": 50, "composition": {"A": 1.0}},
        ],
        "blocks": [{"name": "COL1", "type": "RADFRAC"}],
    })

    with pytest.raises(ValidationError) as exc_info:
        generate_inp(spec)

    assert "RADFRAC" in exc_info.value.report["errors"][0]["message"]
    assert exc_info.value.report["errors"][0]["location"] == "blocks[0].type"


def test_edge_cases_optional_fields():
    spec = PlantSpecification(**{
        "metadata": {
            "title": "Edge Case",
            "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}
        },
        "components": [{"id": "A", "name": "A"}],
        "properties": {"method": "IDEAL"},
        "flowsheet": [{"block": "B1", "inputs": ["S1"], "outputs": ["S2"]}],
        "streams": [
            {"name": "S1", "temperature": 25, "pressure": 1, "mass_flow": 1, "composition": {"A": 1.0}},
            {"name": "S2", "temperature": 25, "pressure": 1, "mole_flow": 1, "composition": {"A": 1.0}}
        ],
        "blocks": [
            {"name": "B1", "type": "MIXER", "parameters": {}},
            {"name": "B2", "type": "MIXER"}
        ]
    })

    inp = generate_inp(spec)
    assert "BLOCK B1 MIXER" in inp
    assert "BLOCK B2 MIXER" in inp
    assert "CHEMISTRY" not in inp


def test_flowsheeting_options():
    spec = PlantSpecification(**{
        "metadata": {
            "title": "Options Test",
            "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}
        },
        "components": [{"id": "H2O", "name": "WATER"}],
        "properties": {"method": "IDEAL"},
        "flowsheet": [{"block": "B1", "inputs": ["S1"], "outputs": ["S2"]}],
        "streams": [
            {"name": "S1", "temperature": 25, "pressure": 1, "mass_flow": 100, "composition": {"H2O": 1.0}},
            {"name": "S2", "temperature": 25, "pressure": 1, "mole_flow": 100, "composition": {"H2O": 1.0}}
        ],
        "blocks": [{"name": "B1", "type": "MIXER"}],
        "flowsheeting_options": {"mass_balance": False, "energy_balance": True}
    })

    inp = generate_inp(spec)
    assert "FLOWSHEETING-OPTIONS" in inp
    assert "MASS-BAL=NO" in inp
    assert "ENERGY-BAL=YES" in inp

    # Test default
    spec_default = PlantSpecification(**{
        "metadata": {
            "title": "Default Options",
            "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"}
        },
        "components": [{"id": "H2O", "name": "WATER"}],
        "properties": {"method": "IDEAL"},
        "flowsheet": [{"block": "B1", "inputs": ["S1"], "outputs": ["S2"]}],
        "streams": [
            {"name": "S1", "temperature": 25, "pressure": 1, "mass_flow": 100, "composition": {"H2O": 1.0}},
            {"name": "S2", "temperature": 25, "pressure": 1, "mole_flow": 100, "composition": {"H2O": 1.0}}
        ],
        "blocks": [{"name": "B1", "type": "MIXER"}]
    })
    inp_default = generate_inp(spec_default)
    assert "FLOWSHEETING-OPTIONS" in inp_default
    assert "MASS-BAL=YES" in inp_default
    assert "ENERGY-BAL=YES" in inp_default


def test_validate_inp_missing_mandatory_sections():
    # Construct a minimal valid INP content but missing STREAM and BLOCK
    inp = """TITLE 'Test'
IN-UNITS MET PRESSURE=BAR TEMPERATURE=C FLOW='KG/HR'
DEF-STREAMS CONVEN ALL
DATABANKS 'APV140 PURE32'
PROP-SOURCES 'APV140 PURE32'
COMPONENTS
    H2O WATER /
PROPERTIES STEAM-TA
FLOWSHEETING-OPTIONS
    MASS-BAL=YES ENERGY-BAL=YES
FLOWSHEET
    BLOCK B1 IN=S1 OUT=S2
"""
    # Should fail because STREAM and BLOCK are now mandatory
    report = validate_inp(inp)
    assert not report["valid"]
    errors = [e["message"] for e in report["errors"]]
    assert "Missing required section 'STREAM'" in errors
    assert "Missing required section 'BLOCK'" in errors


def test_validate_inp_missing_flowsheeting_options():
    # Construct a valid INP but remove FLOWSHEETING-OPTIONS
    inp = """TITLE 'Test'
IN-UNITS MET PRESSURE=BAR TEMPERATURE=C FLOW='KG/HR'
DEF-STREAMS CONVEN ALL
DATABANKS 'APV140 PURE32'
PROP-SOURCES 'APV140 PURE32'
COMPONENTS
    H2O WATER /
PROPERTIES STEAM-TA
FLOWSHEET
    BLOCK B1 IN=S1 OUT=S2
STREAM S1
    SUBSTREAM MIXED TEMP=100.0 PRES=1.0 &
    MASS-FLOW=1000.0
    MASS-FRAC
        H2O 1.0 /
BLOCK B1 HEATER
    PARAM
    TEMP=150.0 PRES=0.0
"""
    # Should fail because FLOWSHEETING-OPTIONS is now mandatory
    report = validate_inp(inp)
    assert not report["valid"]
    errors = [e["message"] for e in report["errors"]]
    assert "Missing required section 'FLOWSHEETING-OPTIONS'" in errors


def test_validate_inp_out_of_order():
    # Construct an INP where BLOCK comes before STREAM
    inp = """TITLE 'Test'
IN-UNITS MET PRESSURE=BAR TEMPERATURE=C FLOW='KG/HR'
DEF-STREAMS CONVEN ALL
DATABANKS 'APV140 PURE32'
PROP-SOURCES 'APV140 PURE32'
COMPONENTS
    H2O WATER /
PROPERTIES STEAM-TA
FLOWSHEETING-OPTIONS
    MASS-BAL=YES ENERGY-BAL=YES
FLOWSHEET
    BLOCK B1 IN=S1 OUT=S2
BLOCK B1 HEATER
    PARAM
    TEMP=150.0 PRES=0.0
STREAM S1
    SUBSTREAM MIXED TEMP=100.0 PRES=1.0 &
    MASS-FLOW=1000.0
    MASS-FRAC
        H2O 1.0 /
"""
    # Should fail because BLOCK is before STREAM
    report = validate_inp(inp)
    assert not report["valid"]
    errors = [e["message"] for e in report["errors"]]
    assert any("Section 'BLOCK' is out of order" in e for e in errors)


def test_validate_inp_optional_sections():
    # Construct an INP with CHEMISTRY (optional) in correct place
    inp = """TITLE 'Test'
IN-UNITS MET PRESSURE=BAR TEMPERATURE=C FLOW='KG/HR'
DEF-STREAMS CONVEN ALL
DATABANKS 'APV140 PURE32'
PROP-SOURCES 'APV140 PURE32'
COMPONENTS
    H2O WATER /
PROPERTIES STEAM-TA
FLOWSHEETING-OPTIONS
    MASS-BAL=YES ENERGY-BAL=YES
FLOWSHEET
    BLOCK B1 IN=S1 OUT=S2
STREAM S1
    SUBSTREAM MIXED TEMP=100.0 PRES=1.0 &
    MASS-FLOW=1000.0
    MASS-FRAC
        H2O 1.0 /
BLOCK B1 HEATER
    PARAM
    TEMP=150.0 PRES=0.0
CHEMISTRY GLOBAL
    STOIC 1 &
        H2O -1.0 /
"""
    # Should be valid
    report = validate_inp(inp)
    if not report["valid"]:
        print("\nERRORS found in valid case:")
        for e in report["errors"]:
            print(f"- {e['message']}")
    assert report["valid"]

    # Now verify that duplicate CHEMISTRY sections or out-of-order optional sections trigger errors
    # Move CHEMISTRY before BLOCK
    inp_bad = """TITLE 'Test'
IN-UNITS MET PRESSURE=BAR TEMPERATURE=C FLOW='KG/HR'
DEF-STREAMS CONVEN ALL
DATABANKS 'APV140 PURE32'
PROP-SOURCES 'APV140 PURE32'
COMPONENTS
    H2O WATER /
PROPERTIES STEAM-TA
FLOWSHEETING-OPTIONS
    MASS-BAL=YES ENERGY-BAL=YES
FLOWSHEET
    BLOCK B1 IN=S1 OUT=S2
STREAM S1
    SUBSTREAM MIXED TEMP=100.0 PRES=1.0 &
    MASS-FLOW=1000.0
    MASS-FRAC
        H2O 1.0 /
CHEMISTRY GLOBAL
    STOIC 1 &
        H2O -1.0 /
BLOCK B1 HEATER
    PARAM
    TEMP=150.0 PRES=0.0
"""
    report_bad = validate_inp(inp_bad)
    assert not report_bad["valid"]
    errors = [e["message"] for e in report_bad["errors"]]
    # CHEMISTRY (optional) found before BLOCK (mandatory) -> BLOCK out of order
    # Because validation checks order of ALL found sections: 
    # ..., STREAM, CHEMISTRY, BLOCK
    # Expected: ..., STREAM, BLOCK, CHEMISTRY
    # So when it sees BLOCK after CHEMISTRY, checks if BLOCK index > CHEMISTRY index?
    # Actually logic is: iterate ALL_SECTION_ORDER.
    # last_line tracks position of previous expected section found.
    # 1. STREAM found at line X. last_line=X.
    # 2. BLOCK found at line Z (Z > Y). last_line=Z.
    # 3. CHEMISTRY found at line Y (Y < Z). 
    # Wait, if I iterate section order:
    # ...
    # STREAM: found at X
    # BLOCK: found at Z
    # CHEMISTRY: found at Y. 
    # If Y < Z, then correct?
    # ALL_SECTION_ORDER = [..., STREAM, BLOCK, CHEMISTRY]
    # Iteration:
    # - STREAM: found at X. last_line=X
    # - BLOCK: found at Z. check Z > X? Yes. last_line=Z.
    # - CHEMISTRY: found at Y. check Y > Z? No (since Y < Z in bad input). Error!
    
    assert any("Section 'CHEMISTRY' is out of order" in e for e in errors)


def test_compr_type_parameter_maps_to_stype():
    """COMPR blocks with a 'TYPE' parameter must emit 'STYPE' in the INP.

    Aspen Plus COMPR uses STYPE (not TYPE) for the compression model selector.
    Emitting TYPE=ISENTROPIC is silently ignored by the simulator, leaving the
    compressor at its default type.
    """
    spec = PlantSpecification(**{
        "metadata": {
            "title": "Compressor STYPE",
            "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"},
        },
        "components": [{"id": "A", "name": "A"}],
        "properties": {"method": "NRTL"},
        "flowsheet": [{"block": "C1", "inputs": ["FEED"], "outputs": ["PROD"]}],
        "streams": [
            {"name": "FEED", "temperature": 25, "pressure": 1, "mass_flow": 100, "composition": {"A": 1.0}},
            {"name": "PROD", "temperature": 25, "pressure": 5, "mass_flow": 100, "composition": {"A": 1.0}},
        ],
        "blocks": [
            {"name": "C1", "type": "COMPR", "parameters": {"PRES": 5, "TYPE": "ISENTROPIC", "EFF": 0.85}}
        ],
    })

    inp = generate_inp(spec)

    assert "STYPE=ISENTROPIC" in inp, "Expected STYPE keyword in COMPR block INP output"
    bare_type_lines = [l.strip() for l in inp.splitlines() if "TYPE=" in l and not l.strip().startswith("S")]
    assert not bare_type_lines, f"Must not emit bare TYPE= for COMPR (Aspen ignores it): {bare_type_lines}"
    assert "EFF=0.85" in inp
    assert "PRES=5.0" in inp
