from aspen_automation import load_spec, generate_inp
import os

def test_to_file():
    fixture_path = r"c:\Users\domingueza\ASPEN_PY\tests\fixtures\valid_plant.yaml"
    spec = load_spec(fixture_path)
    
    # Generate INP
    output_path = "generated_test.inp"
    generate_inp(spec, output_path=output_path)
    
    with open(output_path, "r") as f:
        content = f.read()
    
    print("--- CONTENT ---")
    print(content)
    print("--- END ---")

if __name__ == "__main__":
    test_to_file()
