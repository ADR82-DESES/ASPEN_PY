import yaml
import sys
from pathlib import Path
from aspen_automation.inp_generator import generate_inp

def test_gen():
    yaml_path = Path("C:\\Users\\domingueza\\ASPEN_PY\\templates\\methanol_plant_atr.yaml")
    with open(yaml_path, 'r', encoding='utf-8') as f:
        spec = yaml.safe_load(f)
    
    inp_content = generate_inp(spec)
    out_path = Path("C:\\Users\\domingueza\\ASPEN_PY\\Methanol Plant\\MethanolPlant_generated.inp")
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(inp_content)
    
    print(f"Generated {out_path}")

if __name__ == '__main__':
    test_gen()
