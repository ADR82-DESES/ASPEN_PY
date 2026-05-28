import os
import re
import shutil
import uuid
import pytest

from aspen_automation.exceptions import ValidationError
from aspen_automation.inp_generator import generate_inp, validate_inp
from aspen_automation.schema import PlantSpecification, VALID_BLOCK_TYPES
from aspen_automation.parser import load_spec

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
REFERENCE_DIR = os.path.join(os.path.dirname(__file__), "..", "archive", "aspen_artifacts", "Methanol Plant")


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
    assert "SUBSTREAM MIXED TEMP=100.0 PRES=1.0 MASS-FLOW=1000.0" in inp
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


def test_methanol_template_stream_compositions_use_aspen_sentence_syntax():
    path = os.path.join(os.path.dirname(__file__), "..", "templates", "methanol_plant_atr.yaml")
    spec = load_spec(path)
    inp = generate_inp(spec)
    report = validate_inp(inp)

    assert report["valid"]
    assert not any(
        re.match(r"\s+(?:MOLE|MASS)-FRAC\s*$", line)
        for line in inp.splitlines()
    )
    assert "    MOLE-FRAC O2 0.995 / N2 0.005" in inp


def test_validate_inp_rejects_header_only_composition_sentence():
    inp = """TITLE 'Bad Composition'
IN-UNITS MET PRESSURE=BAR TEMPERATURE=C FLOW='KG/HR'
DEF-STREAMS CONVEN ALL
DATABANKS 'APV140 PURE32'
PROP-SOURCES 'APV140 PURE32'
COMPONENTS
    H2O WATER /
    ET-OH ETHANOL /
PROPERTIES NRTL
FLOWSHEET
    BLOCK B1 IN=S1 OUT=S2
STREAM S1
    SUBSTREAM MIXED TEMP=25.0 PRES=1.0 MASS-FLOW=100.0
    MOLE-FRAC H2O 0.5
    MOLE-FRAC ET-OH 0.5
STREAM S2
    SUBSTREAM MIXED TEMP=25.0 PRES=1.0 MASS-FLOW=100.0
    MOLE-FRAC
BLOCK B1 MIXER
"""

    report = validate_inp(inp)

    assert not report["valid"]
    assert any("Composition sentence missing component/fraction pairs" in e["message"] for e in report["errors"])


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
    assert "STOIC 1 A -1.0 / B 1.0" in inp


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
    assert "    MOLE-FRAC H2O 1.0" in inp


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
    assert "STOIC 1 A -1.0 / B 1.0" in inp
    assert "STOIC 2 B -1.0 / C 1.0" in inp


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
    assert "BLOCK R1 REQUIL" in inp
    assert "PARAM NREAC=1.0" in inp
    assert "STOIC CID=A COEF=-1.0 / CID=B COEF=1.0" in inp
    assert "REACTIONS RXN-SET1" not in inp


def test_rplug_powerlaw_kinetic_reactions_emit_without_methanation():
    assert "RPLUG" in VALID_BLOCK_TYPES
    spec = PlantSpecification(**{
        "metadata": {
            "title": "Kinetic Methanol",
            "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"},
        },
        "components": [
            {"id": "CO", "name": "CARBON-MONOXIDE"},
            {"id": "H2", "name": "HYDROGEN"},
            {"id": "CH3OH", "name": "METHANOL"},
            {"id": "CH4", "name": "METHANE"},
        ],
        "properties": {"method": "RK-SOAVE"},
        "kinetic_models": [
            {
                "id": "VBF96_SCREENING",
                "implementation": "POWERLAW screening surrogate for RPLUG",
            }
        ],
        "flowsheet": [{"block": "B-SYN", "inputs": ["R-IN"], "outputs": ["R-OUT"]}],
        "streams": [
            {
                "name": "R-IN",
                "temperature": 250,
                "pressure": 80,
                "mass_flow": 1000,
                "composition": {"CO": 0.25, "H2": 0.7, "CH4": 0.05},
            },
            {
                "name": "R-OUT",
                "temperature": 250,
                "pressure": 80,
                "mass_flow": 1000,
                "composition": {"CO": 0.2, "H2": 0.65, "CH3OH": 0.1, "CH4": 0.05},
            },
        ],
        "blocks": [
            {
                "name": "B-SYN",
                "type": "RPLUG",
                "parameters": {"TEMP": 250, "PRES": 80, "LENGTH": 8.0, "DIAM": 4.0, "NPOINT": 20},
                "reactions": "RXN-SET1",
            }
        ],
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
    })

    inp = generate_inp(spec)

    assert "BLOCK B-SYN RPLUG" in inp
    assert "PARAM TYPE=T-SPEC LENGTH=8.0 DIAM=4.0 PRES=80.0 NPOINT=20" in inp
    assert "T-SPEC 0.0 250.0 / 1.0 250.0" in inp
    assert "    REACTIONS RXN-SET1" in inp
    assert "REACTIONS RXN-SET1 POWERLAW" in inp
    assert "REAC-DATA 1 KINETIC PHASE=V CBASIS=MOLARITY" in inp
    assert "STOIC 1 MIXED CO -1.0 / H2 -2.0 / CH3OH 1.0" in inp
    assert "RATE-CON 1 0.0001 60000.0" in inp
    assert "CHEMISTRY" not in inp
    assert "RBASIS=" not in inp
    stoic_lines = [line for line in inp.splitlines() if line.strip().startswith("STOIC")]
    assert not any("CH4" in line for line in stoic_lines)


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
    assert "BLOCK SEP1 SEP\n    FRAC STRM=PROD COMPS=A B FRACS=0.99 0.01" in inp
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

    assert "SEFF=0.85" in inp
    assert not re.search(r"(?<!S)\bEFF=0\.85\b", inp)


def test_generate_inp_rejects_radfrac_without_settings():
    spec = {
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
    }

    with pytest.raises(ValidationError) as exc_info:
        generate_inp(spec)

    assert "RADFRAC" in str(exc_info.value.report["errors"])


def test_generate_inp_emits_valve_block():
    spec = PlantSpecification(**{
        "metadata": {
            "title": "Valve",
            "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"},
        },
        "components": [{"id": "A", "name": "A"}],
        "properties": {"method": "NRTL"},
        "flowsheet": [{"block": "V1", "inputs": ["FEED"], "outputs": ["PROD"]}],
        "streams": [
            {"name": "FEED", "temperature": 25, "pressure": 10, "mass_flow": 100, "composition": {"A": 1.0}},
            {"name": "PROD", "temperature": 25, "pressure": 1.8, "mass_flow": 100, "composition": {"A": 1.0}},
        ],
        "blocks": [{"name": "V1", "type": "VALVE", "parameters": {"P-OUT": 1.8}}],
    })

    inp = generate_inp(spec)

    assert "BLOCK V1 VALVE\n    PARAM P-OUT=1.8" in inp


def test_generate_inp_emits_radfrac_block():
    spec = PlantSpecification(**{
        "metadata": {
            "title": "Column",
            "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"},
        },
        "components": [
            {"id": "A", "name": "A"},
            {"id": "B", "name": "B"},
        ],
        "properties": {"method": "NRTL"},
        "flowsheet": [{"block": "COL1", "inputs": ["FEED"], "outputs": ["DIST", "BOT"]}],
        "streams": [
            {"name": "FEED", "temperature": 25, "pressure": 1.8, "mass_flow": 100, "composition": {"A": 0.5, "B": 0.5}},
            {"name": "DIST", "temperature": 25, "pressure": 1.5, "mass_flow": 50, "composition": {"A": 0.99, "B": 0.01}},
            {"name": "BOT", "temperature": 25, "pressure": 2.08, "mass_flow": 50, "composition": {"A": 0.01, "B": 0.99}},
        ],
        "blocks": [
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
            }
        ],
    })

    inp = generate_inp(spec)

    assert "BLOCK COL1 RADFRAC" in inp
    assert "PARAM NSTAGE=30 ALGORITHM=STANDARD MAXOL=50 DAMPING=NONE" in inp
    assert "COL-CONFIG CONDENSER=TOTAL" in inp
    assert "FEEDS FEED 16" in inp
    assert "PRODUCTS DIST 1 L / BOT 30 L" in inp
    assert "P-SPEC 1 1.5" in inp
    assert "COL-SPECS DP-COL=0.58 MASS-B=50.0 MASS-RR=2.0" in inp
    assert "TRAY-REPORT TRAY-OPTION=ALL-TRAYS" in inp


def test_generate_inp_emits_canonical_methanol_lights_recovery_section():
    spec = PlantSpecification(**load_spec(os.path.join(os.path.dirname(__file__), "..", "process_library", "methanol", "process.yaml")))

    inp = generate_inp(spec)

    assert "BLOCK B-LCOOL HEATER" in inp
    assert "PARAM TEMP=50.0 PRES=1.8" in inp
    assert "BLOCK B-LFLA FLASH2" in inp
    assert "BLOCK MIX-COL MIXER" in inp
    assert "BLOCK B-PDEG FLASH2" in inp
    assert "BLOCK MIX-VENT MIXER" in inp
    assert "BLOCK B-DEGAS IN=CRUDE-LP OUT=LIGHTS CLIQ-RAW" in inp
    assert "BLOCK B-LCOOL IN=LIGHTS OUT=LGT-CLD" in inp
    assert "BLOCK B-LFLA IN=LGT-CLD OUT=VENT-GAS REC-MEOH" in inp
    assert "BLOCK MIX-COL IN=CLIQ-RAW REC-MEOH OUT=CRUDE-LQ" in inp
    assert "BLOCK B-DIST IN=CRUDE-LQ OUT=MEOH-RAW WASTE-H2O" in inp
    assert "BLOCK B-PDEG IN=MEOH-RAW OUT=PRO-VENT MEOH-PRO" in inp
    assert "BLOCK MIX-VENT IN=VENT-GAS PRO-VENT OUT=VENT-TOT" in inp
    assert "FEEDS CRUDE-LQ 16" in inp


def test_generate_inp_includes_nrtl_binary_parameter_databanks():
    spec = PlantSpecification(**{
        "metadata": {
            "title": "NRTL Databank Source",
            "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"},
        },
        "components": [
            {"id": "CH3OH", "name": "METHANOL"},
            {"id": "H2O", "name": "WATER"},
        ],
        "properties": {
            "method": "NRTL",
            "databanks": ["APV140 PURE32"],
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
        },
        "flowsheet": [{"block": "B1", "inputs": ["FEED"], "outputs": ["PROD"]}],
        "streams": [
            {
                "name": "FEED",
                "temperature": 25,
                "pressure": 1,
                "mass_flow": 100,
                "composition": {"CH3OH": 0.5, "H2O": 0.5},
            },
            {
                "name": "PROD",
                "temperature": 25,
                "pressure": 1,
                "mass_flow": 100,
                "composition": {"CH3OH": 0.5, "H2O": 0.5},
            },
        ],
        "blocks": [{"name": "B1", "type": "MIXER"}],
    })

    inp = generate_inp(spec)

    assert "PROPERTIES NRTL" in inp
    assert "DATABANKS 'APV140 PURE32' / 'APV140 VLE-IG' / 'APV140 VLE-LIT' / &" in inp
    assert "PROP-SOURCES 'APV140 PURE32' / 'APV140 VLE-IG' / 'APV140 VLE-LIT'" in inp


def test_generate_inp_rejects_explicit_nrtl_binary_parameters_until_emitter_is_verified():
    spec = PlantSpecification(**{
        "metadata": {
            "title": "Explicit NRTL",
            "units": {"pressure": "bar", "temperature": "C", "flow": "kg/hr"},
        },
        "components": [
            {"id": "CH3OH", "name": "METHANOL"},
            {"id": "H2O", "name": "WATER"},
        ],
        "properties": {
            "method": "NRTL",
            "binary_parameters": [
                {
                    "components": ["CH3OH", "H2O"],
                    "model": "NRTL",
                    "source_type": "explicit",
                    "values": {"aij": 1.0, "aji": 2.0, "cij": 0.3},
                    "basis": "Aspen NRTL GAMKIJ 12-value form",
                    "provenance": {"source": "test-only verified syntax placeholder"},
                }
            ],
        },
        "flowsheet": [{"block": "B1", "inputs": ["FEED"], "outputs": ["PROD"]}],
        "streams": [
            {
                "name": "FEED",
                "temperature": 25,
                "pressure": 1,
                "mass_flow": 100,
                "composition": {"CH3OH": 0.5, "H2O": 0.5},
            },
            {
                "name": "PROD",
                "temperature": 25,
                "pressure": 1,
                "mass_flow": 100,
                "composition": {"CH3OH": 0.5, "H2O": 0.5},
            },
        ],
        "blocks": [{"name": "B1", "type": "MIXER"}],
    })

    with pytest.raises(ValidationError) as exc_info:
        generate_inp(spec)

    error = exc_info.value.report["errors"][0]
    assert error["location"] == "properties.binary_parameters[0].source_type"
    assert "Explicit numeric NRTL binary-parameter INP emission is not yet enabled" in error["message"]


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
    assert "FLOWSHEETING-OPTIONS" not in inp
    assert "MASS-BAL=NO" not in inp
    assert "ENERGY-BAL=YES" not in inp

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
    assert "FLOWSHEETING-OPTIONS" not in inp_default
    assert "MASS-BAL=YES" not in inp_default
    assert "ENERGY-BAL=YES" not in inp_default


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


def test_validate_inp_allows_omitted_flowsheeting_options():
    # Aspen V14 batch translation accepts the canonical sections without
    # the legacy FLOWSHEETING-OPTIONS paragraph.
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
    SUBSTREAM MIXED TEMP=100.0 PRES=1.0 MASS-FLOW=1000.0
    MASS-FRAC H2O 1.0
BLOCK B1 HEATER
    PARAM TEMP=150.0 PRES=0.0
"""
    report = validate_inp(inp)
    assert report["valid"], report["errors"]


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
FLOWSHEET
    BLOCK B1 IN=S1 OUT=S2
BLOCK B1 HEATER
    PARAM TEMP=150.0 PRES=0.0
STREAM S1
    SUBSTREAM MIXED TEMP=100.0 PRES=1.0 MASS-FLOW=1000.0
    MASS-FRAC H2O 1.0
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
FLOWSHEET
    BLOCK B1 IN=S1 OUT=S2
STREAM S1
    SUBSTREAM MIXED TEMP=100.0 PRES=1.0 MASS-FLOW=1000.0
    MASS-FRAC H2O 1.0
BLOCK B1 HEATER
    PARAM TEMP=150.0 PRES=0.0
CHEMISTRY GLOBAL
    STOIC 1 H2O -1.0
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
FLOWSHEET
    BLOCK B1 IN=S1 OUT=S2
STREAM S1
    SUBSTREAM MIXED TEMP=100.0 PRES=1.0 MASS-FLOW=1000.0
    MASS-FRAC H2O 1.0
CHEMISTRY GLOBAL
    STOIC 1 H2O -1.0
BLOCK B1 HEATER
    PARAM TEMP=150.0 PRES=0.0
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


def test_compr_type_parameter_keeps_batch_type_and_maps_efficiency():
    """COMPR batch INP uses TYPE plus SEFF for isentropic efficiency."""
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

    assert "TYPE=ISENTROPIC" in inp
    assert "SEFF=0.85" in inp
    assert " EFF=0.85" not in inp
    assert "PRES=5.0" in inp
