from __future__ import annotations

from pathlib import Path

import pytest

from aspen_automation.capsule_runner import resolve_capsule_job


ROOT = Path(__file__).resolve().parents[2]


def test_resolve_capsule_job_uses_process_dir_as_canonical_input() -> None:
    job = {
        "process_dir": "process_library/methanol",
        "spec_path": "process_library/methanol/process.yaml",
        "runs_root": "test_results/capsule_job",
    }

    resolved = resolve_capsule_job(job, base_dir=ROOT)

    assert resolved["process_dir"] == (ROOT / "process_library" / "methanol").resolve()
    assert resolved["spec_path"] == (ROOT / "process_library" / "methanol" / "process.yaml").resolve()
    assert resolved["runs_root"] == (ROOT / "test_results" / "capsule_job").resolve()
    assert resolved["enforce_acceptance_targets"] is False


def test_resolve_capsule_job_rejects_conflicting_spec_path() -> None:
    job = {
        "process_dir": "process_library/methanol",
        "spec_path": "templates/methanol_plant_atr.yaml",
    }

    with pytest.raises(ValueError, match="process_dir as the canonical input"):
        resolve_capsule_job(job, base_dir=ROOT)


def test_resolve_capsule_job_requires_process_dir() -> None:
    with pytest.raises(ValueError, match="requires process_dir"):
        resolve_capsule_job({"spec_path": "process_library/methanol/process.yaml"}, base_dir=ROOT)
