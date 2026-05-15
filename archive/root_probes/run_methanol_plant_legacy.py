from __future__ import annotations

import datetime
import json
import os
import sys

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from aspen_automation import extract_results, generate_inp, load_spec, run_simulation_session
from aspen_automation.exceptions import (
    BuildError,
    ExtractionError,
    ValidationError,
)
from aspen_automation.session import _cleanup_session

RUN_TIMEOUT_SECONDS = 1800
BASE_DIR = SCRIPT_DIR
YAML_PATH = os.path.join(BASE_DIR, "templates", "methanol_plant_atr.yaml")
PLANT_DIR = os.path.join(BASE_DIR, "Methanol Plant")
GENERATED_INP_PATH = os.path.join(PLANT_DIR, "MethanolPlant_generated.inp")
OUTPUT_APW_PATH = os.path.join(PLANT_DIR, "MethanolPlant_output.apw")
RESULTS_DIR = os.path.join(PLANT_DIR, "results")
SESSION_TEMP_DIR = os.path.join(BASE_DIR, "Methanol_Session")
SESSION_TEMP_INP_PATH = os.path.join(SESSION_TEMP_DIR, "temp_simulation.inp")


def log(level: str, message: str) -> None:
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {level}: {message}")


def _log_session_result(session_result) -> None:
    log(
        "INFO",
        (
            "SESSION_BUILD_COMPLETE - "
            f"build_mode={session_result.build_mode}, "
            f"build_mechanism={session_result.build_mechanism_used}"
        ),
    )

    if session_result.build_fallback_attempted:
        log(
            "WARNING",
            "BUILD_FALLBACK_ATTEMPTED - Primary build path failed; fallback path was attempted.",
        )
        init_error = session_result.diagnostics.get("InitFromFile2_error")
        if init_error:
            log("WARNING", f"BUILD_PRIMARY_ERROR - {init_error}")

    log(
        "INFO",
        (
            "SESSION_RUN_COMPLETE - "
            f"status={session_result.convergence_status}, "
            f"simulation_time_seconds={session_result.simulation_time_seconds:.2f}"
        ),
    )


def _write_results(results, simulation_time_seconds: float) -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)

    streams_path = os.path.join(RESULTS_DIR, "streams.csv")
    blocks_path = os.path.join(RESULTS_DIR, "blocks.csv")
    kpis_path = os.path.join(RESULTS_DIR, "kpis.json")

    results["streams"].to_csv(streams_path, index=False)
    results["blocks"].to_csv(blocks_path, index=False)

    kpis = results.get("kpis")
    if not isinstance(kpis, dict):
        kpis = {}
    else:
        kpis = dict(kpis)
    kpis["simulation_time_seconds"] = simulation_time_seconds

    with open(kpis_path, "w", encoding="utf-8") as handle:
        json.dump(kpis, handle, indent=2)


def main() -> int:
    session_result = None
    aspen = None

    try:
        os.makedirs(PLANT_DIR, exist_ok=True)

        log("INFO", f"Loading plant specification from YAML: {YAML_PATH}")
        spec = load_spec(YAML_PATH)

        log("INFO", f"Generating INP debug artifact: {GENERATED_INP_PATH}")
        generate_inp(spec, output_path=GENERATED_INP_PATH)

        log("INFO", "SESSION_START - Connecting to Aspen Plus and running simulation session.")
        session_result = run_simulation_session(
            spec,
            build_mode="auto",
            output_dir=SESSION_TEMP_DIR,
            keep_alive=True,
            timeout_seconds=RUN_TIMEOUT_SECONDS,
            visible=True,
        )
        _log_session_result(session_result)
        aspen = session_result.aspen

        if aspen is None:
            raise RuntimeError("Session did not return a live Aspen object.")

        status = str(session_result.convergence_status).strip().lower()
        if status == "timeout":
            log("ERROR", f"TIMEOUT - Simulation exceeded {RUN_TIMEOUT_SECONDS}s")
            return 5
        if status == "failed":
            log("ERROR", "SIMULATION_FAILED - Aspen run finished but did not converge.")
            return 3
        if status == "unknown":
            log(
                "ERROR",
                f"SIMULATION_STATUS_UNKNOWN - Aspen run returned unsupported status: {session_result.convergence_status!r}",
            )
            return 3
        if status != "converged":
            log(
                "ERROR",
                f"SIMULATION_STATUS_UNKNOWN - Aspen run returned unsupported status: {session_result.convergence_status!r}",
            )
            return 3

        try:
            log("INFO", f"Saving output APW: {OUTPUT_APW_PATH}")
            aspen.SaveAs(OUTPUT_APW_PATH)
            log("OK", f"OUTPUT_SAVED - {OUTPUT_APW_PATH}")
        except Exception as save_exc:
            log("ERROR", f"OUTPUT_SAVE_FAILED - {save_exc}")
            return 2

        try:
            log("INFO", "Extracting simulation results...")
            results = extract_results(aspen, spec)
            _write_results(results, simulation_time_seconds=session_result.simulation_time_seconds)
            log("OK", f"Results saved to {RESULTS_DIR}")
        except ExtractionError as extraction_exc:
            log("WARNING", f"EXTRACTION_FAILED - {extraction_exc}")
            return 0

        return 0

    except ValidationError as spec_exc:
        log("ERROR", f"SPEC_INVALID - {spec_exc}")
        return 1
    except BuildError as build_exc:
        log("ERROR", f"BUILD_FAILED - {build_exc}")
        return 3
    except Exception as unexpected_exc:
        log("ERROR", f"UNEXPECTED - {unexpected_exc}")
        return 1
    finally:
        if aspen is not None:
            log("INFO", f"DEBUG: Clean-up disabled for inspection. Session dir: {SESSION_TEMP_DIR}")
            # _cleanup_session(aspen, output_dir=SESSION_TEMP_DIR, keep_alive=False)


if __name__ == "__main__":
    sys.exit(main())
