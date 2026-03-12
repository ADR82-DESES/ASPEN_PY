from pathlib import Path
import subprocess

models = ['CHEMEQ', 'EQUI', 'EQUILIBRIUM', 'KEQUI', 'EQUIL', '']

for model in models:
    inp_content = f"""TITLE 'Test Reactions'
IN-UNITS MET PRESSURE=BAR TEMPERATURE=C FLOW='KG/HR'
DEF-STREAMS CONVEN ALL
DATABANKS 'APV140 PURE32' / 'APV140 AQUEOUS' / 'NOASPENPCD'
PROP-SOURCES 'APV140 PURE32' / 'APV140 AQUEOUS'
COMPONENTS
    CH4 METHANE / H2O WATER / CO CARBON-MONOXIDE /
    CO2 CARBON-DIOXIDE / H2 HYDROGEN / CH3OH METHANOL
PROPERTIES RK-SOAVE
FLOWSHEET
    BLOCK B-SYN IN=S1 OUT=S2 S3
STREAM S1
    SUBSTREAM MIXED TEMP=40.0 PRES=30.0 MASS-FLOW=220000.0
    MOLE-FRAC CH4 1.0

BLOCK B-SYN REQUIL
    PARAM TEMP=250.0 PRES=80.0
    REACTIONS RXN-SET1

REACTIONS RXN-SET1 {model}
    REAC-DATA 1
    STOIC 1 CO -1.0 / H2 -2.0 / CH3OH 1.0
    K-STOIC 1 12.28 -4048.0 0.0 0.0
"""
    path = Path("C:\\Users\\domingueza\\ASPEN_PY\\test_models.inp").resolve()
    path.write_text(inp_content)
    subprocess.run([r"C:\Program Files\AspenTech\Aspen Plus V14.0\Engine\Xeq\aspen.exe", str(path)], cwd=str(path.parent), capture_output=True)
    
    with open("C:\\Users\\domingueza\\ASPEN_PY\\test_models.his", 'r') as f:
        content = f.read()
        if "IS NOT A VALID REACTION MODEL" not in content and "SEVERE ERROR" not in content:
            print(f"SUCCESS with model: '{model}'")
            break
        elif "SEVERE" in content:
            # count sever errors
            cnt = content.count("SEVERE")
            print(f"Model '{model}' had {cnt} SEVERE references")
