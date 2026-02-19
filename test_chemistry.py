from aspen_automation import load_spec, generate_inp
import os

def test_chemistry():
    # Use invalid_chemistry.yaml but fix it to be valid for loading if needed,
    # or just use it as is if it loads but has semantic errors (which we don't care about here)
    fixture_path = r"c:\Users\domingueza\ASPEN_PY\tests\fixtures\invalid_chemistry.yaml"
    
    # Actually, let's just construct a spec manually to test chemistry generation
    from aspen_automation.schema import PlantSpecification, Metadata, UnitSystem, Component, Properties, Chemistry, Reaction, ChemistryStoichiometry
    
    spec = PlantSpecification(
        metadata=Metadata(
            title="Chem Test",
            units=UnitSystem(pressure="bar", temperature="C", flow="kg/hr")
        ),
        components=[Component(id="H2", name="HYDROGEN"), Component(id="O2", name="OXYGEN"), Component(id="H2O", name="WATER")],
        properties=Properties(method="STEAM-TA"),
        flowsheet=[],
        streams=[],
        blocks=[],
        chemistry=[
            Chemistry(
                id="C1",
                reactions=[
                    Reaction(
                        id=1,
                        stoichiometry=[
                            ChemistryStoichiometry(component="H2", coefficient=-2.0),
                            ChemistryStoichiometry(component="O2", coefficient=-1.0),
                            ChemistryStoichiometry(component="H2O", coefficient=2.0)
                        ]
                    )
                ]
            )
        ]
    )
    
    inp_content = generate_inp(spec)
    print("--- CHEMISTRY INP ---")
    print(inp_content)
    
    if "CHEMISTRY C1" in inp_content and "STOIC 1 &" in inp_content and "H2 -2.0 / &" in inp_content:
        print("Chemistry generation looks correct.")
    else:
        print("Chemistry generation FAILED.")

if __name__ == "__main__":
    test_chemistry()
