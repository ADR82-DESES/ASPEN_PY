from aspen_automation import run_simulation_session, load_spec
import os
import sys

def main():
    YAML_PATH = "templates/minimal_test.yaml"
    SESSION_DIR = "Methanol_Session_Minimal"
    
    if not os.path.exists(YAML_PATH):
        print(f"Error: {YAML_PATH} not found")
        return 1
        
    try:
        spec = load_spec(YAML_PATH)
        result = run_simulation_session(
            spec,
            build_mode="auto",
            output_dir=SESSION_DIR,
            timeout_seconds=300,
            visible=True,
            keep_alive=True
        )
        
        print(f"Status: {result.convergence_status}")
        print(f"Time: {result.simulation_time_seconds:.2f}s")
        
        aspen = result.aspen
        if aspen:
            print("\nVerifying loaded state...")
            def check_node(path):
                try:
                    node = aspen.Tree.FindNode(path)
                    if node:
                        print(f"[OK] Found: {path}")
                        # If node has values, print them
                        if hasattr(node, "Value") and node.Value is not None:
                            print(f"     Value: {node.Value}")
                    else:
                        print(f"[FAIL] Missing: {path}")
                except Exception as e:
                    print(f"[ERROR] {path}: {e}")

            check_node(r"\Data\Components\Specifications\Selection")
            check_node(r"\Data\Properties\Specifications\Global\Selection")
            check_node(r"\Data\Streams\FEED\Input\TEMP\MIXED")
            check_node(r"\Data\Blocks\B1\Input\TYPE")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
