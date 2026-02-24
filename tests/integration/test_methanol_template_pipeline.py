from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

import aspen_automation.runner as runner_module
import aspen_automation.session as session_module
from aspen_automation import load_spec


class _FakeElement:
    def __init__(self, name: str) -> None:
        self.Name = name


class _FakeElements:
    def __init__(self, names: list[str]) -> None:
        self._names = list(names)
        self.Count = len(self._names)

    def Item(self, index: int) -> _FakeElement:
        return _FakeElement(self._names[index - 1])


class _FakeNode:
    def __init__(self, value: Any = None, element_names: list[str] | None = None) -> None:
        self.Value = value
        self.Elements = _FakeElements(element_names or [])


class _FakeTree:
    def __init__(self, nodes: dict[str, _FakeNode]) -> None:
        self._nodes = nodes

    def FindNode(self, path: str) -> _FakeNode | None:
        return self._nodes.get(path)


class _FakeEngine:
    def __init__(self) -> None:
        self._is_running = False

    def Run2(self, _mode: int) -> None:
        self._is_running = False

    @property
    def IsRunning(self) -> bool:
        return self._is_running

    def Stop(self) -> None:
        self._is_running = False


class _FakeAspen:
    def __init__(self, nodes: dict[str, _FakeNode]) -> None:
        self.Visible = 0
        self.SuppressDialogs = 0
        self.Tree = _FakeTree(nodes)
        self.Engine = _FakeEngine()
        self.loaded_paths: list[str] = []
        self.quit_called = False

    def InitFromFile2(self, path: str) -> None:
        self.loaded_paths.append(path)

    def InitNew(self) -> None:
        return None

    def Import(self, path: str) -> None:
        self.loaded_paths.append(path)

    def ImportSimulation(self, path: str) -> None:
        self.loaded_paths.append(path)

    def Reinit(self) -> None:
        return None

    def Quit(self) -> None:
        self.quit_called = True


def _build_fake_tree_nodes(template_spec: dict[str, Any]) -> dict[str, _FakeNode]:
    component_ids = [str(component["id"]) for component in template_spec["components"]]
    feed_stream_names = [str(stream["name"]) for stream in template_spec["streams"]]
    all_stream_names = set(feed_stream_names)
    for connection in template_spec["flowsheet"]:
        all_stream_names.update(str(stream) for stream in connection.get("inputs", []))
        all_stream_names.update(str(stream) for stream in connection.get("outputs", []))

    block_names = [str(block["name"]) for block in template_spec["blocks"]]
    target_mass_flow = 10000.0 * 1000.0 / 24.0

    stream_data: dict[str, dict[str, Any]] = {}
    for stream in template_spec["streams"]:
        composition = {str(component): float(value) for component, value in stream.get("composition", {}).items()}
        stream_data[str(stream["name"])] = {
            "temperature": float(stream.get("temperature", 40.0)),
            "pressure": float(stream.get("pressure", 30.0)),
            "mass_flow": float(stream.get("mass_flow", 1000.0)),
            "mole_flow": float(stream.get("mass_flow", 1000.0)),
            "mole_fracs": composition.copy(),
            "mass_fracs": composition.copy(),
        }

    # Force KPI/acceptance success for this mocked integration run.
    stream_data["NG-FEED"] = {
        "temperature": 40.0,
        "pressure": 30.0,
        "mass_flow": target_mass_flow,
        "mole_flow": target_mass_flow,
        "mole_fracs": {"CH3OH": 0.999, "H2O": 0.001},
        "mass_fracs": {"CH3OH": 0.999, "H2O": 0.001},
    }
    stream_data["MEOH-PRO"] = {
        "temperature": 40.0,
        "pressure": 1.2,
        "mass_flow": target_mass_flow,
        "mole_flow": target_mass_flow,
        "mole_fracs": {"CH3OH": 0.999, "H2O": 0.001},
        "mass_fracs": {"CH3OH": 0.999, "H2O": 0.001},
    }

    nodes: dict[str, _FakeNode] = {
        r"\Data\Streams": _FakeNode(element_names=sorted(all_stream_names)),
        r"\Data\Blocks": _FakeNode(element_names=block_names),
        r"\Data\Results Summary\Run-Status\Output\PER_ERROR": _FakeNode(0),
        r"\Data\Results Summary\Run-Status\Output\NERROR": _FakeNode(0),
        r"\Data\Results Summary\Run-Status\Output\NWARN": _FakeNode(0),
    }

    for stream_name in sorted(all_stream_names):
        values = stream_data.get(
            stream_name,
            {
                "temperature": 40.0,
                "pressure": 30.0,
                "mass_flow": 1000.0,
                "mole_flow": 1000.0,
                "mole_fracs": {"CH4": 1.0},
                "mass_fracs": {"CH4": 1.0},
            },
        )
        nodes[rf"\Data\Streams\{stream_name}\Output\TEMP_OUT\MIXED"] = _FakeNode(values["temperature"])
        nodes[rf"\Data\Streams\{stream_name}\Output\PRES_OUT\MIXED"] = _FakeNode(values["pressure"])
        nodes[rf"\Data\Streams\{stream_name}\Output\MASSFLMX\MIXED"] = _FakeNode(values["mass_flow"])
        nodes[rf"\Data\Streams\{stream_name}\Output\MOLEFLMX\MIXED"] = _FakeNode(values["mole_flow"])

        mole_fracs = values["mole_fracs"]
        mass_fracs = values["mass_fracs"]
        for component_id in component_ids:
            nodes[rf"\Data\Streams\{stream_name}\Output\MOLEFRAC\MIXED\{component_id}"] = _FakeNode(
                float(mole_fracs.get(component_id, 0.0))
            )
            nodes[rf"\Data\Streams\{stream_name}\Output\MASSFRAC\MIXED\{component_id}"] = _FakeNode(
                float(mass_fracs.get(component_id, 0.0))
            )

    for block in template_spec["blocks"]:
        block_name = str(block["name"])
        block_type = str(block.get("type", "UNKNOWN"))
        nodes[rf"\Data\Blocks\{block_name}\Input\TYPE"] = _FakeNode(block_type)
        nodes[rf"\Data\Blocks\{block_name}\Output\QNET"] = _FakeNode(0.0)
        nodes[rf"\Data\Blocks\{block_name}\Output\WNET"] = _FakeNode(0.0)
        nodes[rf"\Data\Blocks\{block_name}\Output\CONV"] = _FakeNode(1.0)
        nodes[rf"\Data\Blocks\{block_name}\Output\EFF"] = _FakeNode(0.9)

    return nodes


def _track_step(
    name: str,
    fn: Callable[..., Any],
    steps: list[str],
) -> Callable[..., Any]:
    def _wrapped(*args: Any, **kwargs: Any) -> Any:
        steps.append(name)
        return fn(*args, **kwargs)

    return _wrapped


def test_methanol_template_end_to_end_pipeline_with_mocked_aspen(tmp_path: Path) -> None:
    root_dir = Path(__file__).resolve().parents[2]
    template_path = root_dir / "templates" / "methanol_plant_atr.yaml"
    template_spec = load_spec(str(template_path))
    fake_aspen = _FakeAspen(_build_fake_tree_nodes(template_spec))

    observed_steps: list[str] = []
    expected_steps = ["spec", "build", "run", "extract", "report", "acceptance"]

    real_load_spec = runner_module.load_spec
    real_build_auto = session_module._build_auto
    real_run = session_module._run_simulation
    real_extract = runner_module.extract_results
    real_generate_reports = runner_module.generate_reports
    real_validate_acceptance = runner_module.validate_acceptance

    with (
        patch.object(session_module, "_connect_aspen", return_value=fake_aspen),
        patch.object(runner_module, "load_spec", side_effect=_track_step("spec", real_load_spec, observed_steps)),
        patch.object(session_module, "_build_auto", side_effect=_track_step("build", real_build_auto, observed_steps)),
        patch.object(session_module, "_run_simulation", side_effect=_track_step("run", real_run, observed_steps)),
        patch.object(runner_module, "extract_results", side_effect=_track_step("extract", real_extract, observed_steps)),
        patch.object(
            runner_module,
            "generate_reports",
            side_effect=_track_step("report", real_generate_reports, observed_steps),
        ),
        patch.object(
            runner_module,
            "validate_acceptance",
            side_effect=_track_step("acceptance", real_validate_acceptance, observed_steps),
        ),
    ):
        result = runner_module.run_simulation(
            str(template_path),
            build_mode="auto",
            visible=False,
            output_dir=str(tmp_path),
        )

    assert observed_steps == expected_steps
    assert result["acceptance"]["passed"] is True

    report_dir = Path(result["report_dir"])
    assert report_dir.is_dir()
    expected_files = {
        "streams.csv",
        "blocks.csv",
        "material_balance.csv",
        "energy_balance.csv",
        "kpis.json",
        "diagnostics.json",
        "run_summary.html",
    }
    assert expected_files.issubset({path.name for path in report_dir.iterdir()})
