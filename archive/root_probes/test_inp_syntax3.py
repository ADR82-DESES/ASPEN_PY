from pathlib import Path
import subprocess

inp_content = """TITLE 'Test Syntax 3'
IN-UNITS MET PRESSURE=BAR TEMPERATURE=C FLOW='KG/HR'
DEF-STREAMS CONVEN ALL
DATABANKS 'APV140 PURE32' / 'APV140 AQUEOUS' / 'NOASPENPCD'
PROP-SOURCES 'APV140 PURE32' / 'APV140 AQUEOUS'
COMPONENTS
    CH4 METHANE / H2O WATER / CO CARBON-MONOXIDE /
    CO2 CARBON-DIOXIDE / H2 HYDROGEN / CH3OH METHANOL
PROPERTIES RK-SOAVE
FLOWSHEET
    BLOCK MIX1 IN=S1 OUT=S2
    BLOCK B-SYN IN=S2 OUT=S3 S4
STREAM S1
    SUBSTREAM MIXED TEMP=40.0 PRES=30.0 MASS-FLOW=220000.0
    MOLE-FRAC CH4 1.0 / H2O 0.0

BLOCK MIX1 MIXER

BLOCK B-SYN REQUIL
    PARAM TEMP=250.0 PRES=80.0 NREAC=1
    STOIC 1 -1.0 CO / -2.0 H2 / 1.0 CH3OH

"""
path = Path("C:\\Users\\domingueza\\ASPEN_PY\\test_syntax3.inp").resolve()
path.write_text(inp_content)
print("Running Aspen translator...")
subprocess.run([r"C:\Program Files\AspenTech\Aspen Plus V14.0\Engine\Xeq\aspen.exe", str(path)], cwd=str(path.parent))
