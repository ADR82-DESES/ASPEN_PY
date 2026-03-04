import os
import sys
import win32com.client as win32

filepath = r"c:\Users\domingueza\ASPEN_PY\Methanol Plant\MethanolPlant.apw"
aspen = win32.Dispatch('Apwn.Document')
aspen.InitFromArchive2(os.path.abspath(filepath))

run_status = aspen.Tree.FindNode(r"\Data\Results Summary\Run-Status\Output\PER_ERROR")

if run_status is not None:
    val = run_status.Value
    if val == 0:
        print("OK: CONVERGED — PER_ERROR = 0")
        output_path = os.path.join(os.path.dirname(os.path.abspath(filepath)), "MethanolPlant_output.apw")
        try:
            aspen.SaveAs(output_path)
            print(f"OK: OUTPUT_SAVED — {output_path}")
        except Exception as save_exc:
            print(f"ERROR: OUTPUT_SAVE_FAILED — {save_exc}")
    else:
        print(f"WARNING: NOT_CONVERGED — PER_ERROR = {val}")
else:
    print("WARNING: STATUS_UNKNOWN")

aspen.Quit()
print("Done.")
sys.exit(0)
