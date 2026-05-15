from aspen_automation import load_spec, generate_inp
import os

def test_generation():
    fixture_path = r"c:\Users\domingueza\ASPEN_PY\tests\fixtures\valid_plant.yaml"
    spec = load_spec(fixture_path)
    
    # Generate INP
    inp_content = generate_inp(spec)
    
    print("--- Generated INP ---")
    print(inp_content)
    print("--- End of INP ---")
    
    # Basic validation
    from aspen_automation.inp_generator import validate_inp
    report = validate_inp(inp_content)
    print(f"Basic validation: {'Passed' if report['valid'] else 'Failed'}")
    
    # Check for some expected content
    expected = [
        "TITLE 'Methanol Plant 10k TPD'",
        "IN-UNITS MET",
        "COMPONENTS",
        "CH4 METHANE",
        "PROPERTIES RK-SOAVE",
        "FLOWSHEET",
        "BLOCK MIX-FEED IN=NG-FEED IN=STEAM IN=O2-FEED OUT=ATR-IN",
        "STREAM NG-FEED",
        "MASS-FLOW=220000.0",
        "BLOCK B-ATR RGIBBS",
        "TEMP=1000.0"
    ]
    
    all_found = True
    for item in expected:
        if item not in inp_content:
            print(f"MISSING: {item}")
            all_found = False
    
    if all_found:
        print("All expected snippets found.")
    else:
        print("Some snippets missing.")

if __name__ == "__main__":
    test_generation()
