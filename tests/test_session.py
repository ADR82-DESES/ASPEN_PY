import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import sys
import shutil
import uuid
from pathlib import Path
from types import SimpleNamespace

# Mock win32com before import
sys.modules["win32com"] = MagicMock()
sys.modules["win32com.client"] = MagicMock()

from aspen_automation.session import (
    check_aspen_v14_connection,
    run_simulation_session,
    SessionResult,
    AspenConnectionError,
    BuildError,
    SimulationError,
    _connect_aspen,
    _build_inp_only,
    _build_com_only,
    _build_auto,
    _cleanup_session,
    _run_simulation,
    _verify_flowsheet,
    _verify_aspen_v14_connection,
    _import_file_with_verification,
)
from aspen_automation.schema import PlantSpecification, Metadata, UnitSystem, Properties
from aspen_automation.exceptions import ValidationError


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def spec():
    return PlantSpecification(
        metadata=Metadata(title="Test", units=UnitSystem(pressure="bar", temperature="C", flow="kg/hr")),
        components=[],
        properties=Properties(method="NRTL"),
        flowsheet=[],
        streams=[],
        blocks=[]
    )


@pytest.fixture
def output_dir():
    return "test_results"


@pytest.fixture(autouse=True)
def no_default_v14_seed_files():
    with patch("aspen_automation.session.ASPEN_V14_SEED_FILE_CANDIDATES", ()):
        yield


@pytest.fixture
def mock_aspen():
    aspen = MagicMock()
    aspen.Version = "40.0"
    aspen.Engine.IsRunning = False
    mock_node = MagicMock()
    mock_node.Value = 0
    aspen.Tree.FindNode.return_value = mock_node
    return aspen


def _mock_node(value=0, names=None):
    names = list(names or [])
    node = MagicMock()
    node.Value = value
    elements = MagicMock()
    elements.Count = len(names)
    elements.Item.side_effect = lambda index: MagicMock(Name=names[index - 1])
    node.Elements = elements
    return node


def _mock_dispatch(mock_win32, aspen):
    mock_win32.DispatchEx.return_value = aspen
    mock_win32.Dispatch.return_value = aspen


def _mock_dispatch_error(mock_win32, error):
    mock_win32.DispatchEx.side_effect = error
    mock_win32.Dispatch.side_effect = error


def _worker_success(archive_path="compiled_from_inp.bkp"):
    return {
        "generated_inp_path": "temp_simulation.inp",
        "generated_inp_file": {"path": "temp_simulation.inp", "exists": True, "size_bytes": 100},
        "compiled_archive_path": archive_path,
        "compiled_archive_file": {"path": archive_path, "exists": True, "size_bytes": 100},
        "build_mechanism": "InitFromArchive2+Import",
        "import_attempts": [
            {"mechanism": "InitFromArchive2", "path_variant": "v14_seed_file", "success": True},
            {"mechanism": "InitFromArchive2+Import", "path_variant": "raw_string", "success": True},
        ],
        "build_valid": True,
        "flowsheet_verification": {
            "build_valid": True,
            "stream_count": 1,
            "block_count": 1,
            "stream_samples": ["S1"],
            "block_samples": ["B1"],
        },
    }


def _builder_success():
    return {
        "build_mechanism": "com_block_builder",
        "build_valid": True,
        "components_added": ["CH4", "H2O"],
        "streams_created": ["NG-FEED", "STEAM", "O2-FEED"],
        "blocks_created": ["MIX-FEED", "B-ATR"],
        "feed_streams": ["NG-FEED", "STEAM", "O2-FEED"],
        "feed_inputs_configured": ["NG-FEED", "STEAM", "O2-FEED"],
        "flowsheet_verification": {
            "build_valid": True,
            "stream_count": 3,
            "block_count": 2,
            "stream_samples": ["NG-FEED", "STEAM", "O2-FEED"],
            "block_samples": ["MIX-FEED", "B-ATR"],
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_aspen_v14_preflight_success(mock_aspen):
    mock_aspen.Tree.FindNode.return_value = _mock_node()

    diagnostics = _verify_aspen_v14_connection(mock_aspen, visible=False)

    assert diagnostics["connection_verified"] is True
    assert diagnostics["v14_verified"] is True
    assert diagnostics["v14_version_verified"] is True
    assert diagnostics["version_status"] == "v14"
    assert diagnostics["aspen_version"] == "40.0"
    assert diagnostics["data_node_present"] is True
    mock_aspen.InitNew.assert_called_once()
    mock_aspen.Tree.FindNode.assert_called_with(r"\Data")


def test_aspen_v14_preflight_allows_unreported_version_when_tree_is_available(mock_aspen):
    mock_aspen.Version = None
    mock_aspen.Application = object()
    mock_aspen.Tree.FindNode.return_value = _mock_node()

    diagnostics = _verify_aspen_v14_connection(mock_aspen, visible=False)

    assert diagnostics["connection_verified"] is True
    assert diagnostics["v14_verified"] is False
    assert diagnostics["v14_version_verified"] is False
    assert diagnostics["version_status"] == "unreported"
    assert diagnostics["preflight_status"] == "connected_version_unreported"
    assert diagnostics["aspen_version"] is None


def test_aspen_v14_preflight_uses_application_version_when_document_version_missing(mock_aspen):
    mock_aspen.Version = None
    mock_aspen.Application = SimpleNamespace(Version="40.0", Name="Aspen Plus")
    mock_aspen.Tree.FindNode.return_value = _mock_node()

    diagnostics = _verify_aspen_v14_connection(mock_aspen, visible=False)

    assert diagnostics["connection_verified"] is True
    assert diagnostics["v14_verified"] is True
    assert diagnostics["v14_version_verified"] is True
    assert diagnostics["version_status"] == "v14"
    assert diagnostics["aspen_version"] == "40.0"
    assert diagnostics["identity_probe"]["application"]["Version"] == "40.0"


def test_aspen_v14_preflight_allows_unreadable_version_when_tree_is_available():
    class VersionRaisesAspen:
        def __init__(self):
            self.Application = object()
            self.Tree = MagicMock()
            self.Tree.FindNode.return_value = _mock_node()
            self.InitNew = MagicMock()
            self.Visible = 0
            self.SuppressDialogs = 0

        @property
        def Version(self):
            raise Exception("Version unavailable")

    diagnostics = _verify_aspen_v14_connection(VersionRaisesAspen(), visible=False)

    assert diagnostics["connection_verified"] is True
    assert diagnostics["v14_version_verified"] is False
    assert diagnostics["version_status"] == "unreported"
    assert diagnostics["preflight_status"] == "connected_version_unreported"


def test_aspen_v14_preflight_rejects_wrong_version(mock_aspen):
    mock_aspen.Version = "39.0"

    with pytest.raises(AspenConnectionError, match="expected OLE version 40.x"):
        _verify_aspen_v14_connection(mock_aspen)

    mock_aspen.InitNew.assert_not_called()


def test_aspen_v14_preflight_rejects_missing_data_tree(mock_aspen):
    mock_aspen.Tree.FindNode.return_value = None

    with pytest.raises(AspenConnectionError, match="Data node"):
        _verify_aspen_v14_connection(mock_aspen)


def test_check_aspen_v14_connection_fails_without_win32():
    with patch("aspen_automation.session.win32", None):
        with pytest.raises(AspenConnectionError, match="win32com.client is not available"):
            check_aspen_v14_connection()


@patch("aspen_automation.session._connect_aspen")
def test_check_aspen_v14_connection_closes_temporary_document(mock_connect, mock_aspen):
    mock_connect.return_value = mock_aspen
    mock_aspen.Tree.FindNode.return_value = _mock_node()

    diagnostics = check_aspen_v14_connection()

    assert diagnostics["v14_verified"] is True
    mock_aspen.Close.assert_called_once_with(False)
    mock_aspen.Quit.assert_called_once()


# Case 1: inp-only success
@patch("aspen_automation.session.generate_inp")
@patch("aspen_automation.session.win32")
def test_01_inp_only_success(mock_win32, mock_gen, spec, output_dir, mock_aspen):
    _mock_dispatch(mock_win32, mock_aspen)

    result = run_simulation_session(spec, build_mode="inp-only", output_dir=output_dir)

    assert result.build_mode == "inp-only"
    assert result.build_mechanism_used == "InitFromFile2"
    mock_aspen.InitFromFile2.assert_called()
    assert result.convergence_status == "converged"


# Case 2: inp-only fail raises BuildError (Comment 2)
@patch("aspen_automation.session.generate_inp")
@patch("aspen_automation.session.win32")
def test_02_inp_only_fail(mock_win32, mock_gen, spec, output_dir, mock_aspen):
    _mock_dispatch(mock_win32, mock_aspen)
    mock_aspen.InitFromFile2.side_effect = Exception("Init failed")

    with pytest.raises(BuildError, match="Init failed"):
        run_simulation_session(spec, build_mode="inp-only", output_dir=output_dir)


# Case 3: com-only diagnostic success
@patch("aspen_automation.session.win32")
def test_03_com_only_diagnostic(mock_win32, spec, output_dir, mock_aspen):
    _mock_dispatch(mock_win32, mock_aspen)

    result = run_simulation_session(spec, build_mode="com-only", output_dir=output_dir)

    assert result.build_mode == "com-only"
    assert result.build_mechanism_used == "COM"
    mock_aspen.InitNew.assert_called()
    assert "warning" in result.diagnostics


# Case 4: auto primary success
@patch("aspen_automation.session.generate_inp")
@patch("aspen_automation.session.win32")
def test_04_auto_primary_success(mock_win32, mock_gen, spec, output_dir, mock_aspen):
    _mock_dispatch(mock_win32, mock_aspen)

    with patch("aspen_automation.session.build_flowsheet_via_com", return_value=_builder_success()) as mock_builder:
        result = run_simulation_session(spec, build_mode="auto", output_dir=output_dir)

    assert result.build_mode == "auto"
    assert result.build_mechanism_used == "com_block_builder"
    assert not result.build_fallback_attempted
    mock_builder.assert_called_once()
    mock_gen.assert_not_called()
    assert result.diagnostics["build_valid"] is True
    assert result.diagnostics["flowsheet_verification"]["stream_count"] == 3


@patch("aspen_automation.session.generate_inp")
@patch("aspen_automation.session.win32")
def test_auto_builder_failure_preserves_com_builder_diagnostics(
    mock_win32, mock_gen, spec, output_dir, mock_aspen
):
    _mock_dispatch(mock_win32, mock_aspen)
    build_error = BuildError(
        "COM block builder failed: no input connection node found",
        build_mode="auto",
        mechanism_tried="com_block_builder",
        diagnostics={
            "build_mechanism": "com_block_builder",
            "feed_streams": ["NG-FEED"],
            "connections_applied": [],
            "block_creation_attempts": {"MIX-FEED": [{"strategy": "elements_add", "candidate": "MIXER"}]},
        },
    )

    with patch("aspen_automation.session.build_flowsheet_via_com", side_effect=build_error):
        with pytest.raises(BuildError, match="no input connection node found") as exc_info:
            run_simulation_session(spec, build_mode="auto", output_dir=output_dir)

    assert exc_info.value.mechanism_tried == "com_block_builder"
    assert exc_info.value.diagnostics["build_mechanism"] == "com_block_builder"
    assert exc_info.value.diagnostics["feed_streams"] == ["NG-FEED"]

# Case 5: auto batch failure preserves diagnostics
@patch("aspen_automation.session.generate_inp")
@patch("aspen_automation.session.win32")
def test_05_auto_build_error_preserves_diagnostics(mock_win32, mock_gen, spec, output_dir, mock_aspen):
    _mock_dispatch(mock_win32, mock_aspen)
    build_error = BuildError(
        "COM block builder failed: unable to create block 'B-ATR'.",
        build_mode="auto",
        mechanism_tried="com_block_builder",
        diagnostics={
            "build_mechanism": "com_block_builder",
            "block_creation_attempts": {
                "B-ATR": [
                    {"strategy": "elements_add", "candidate": "RGIBBS"},
                    {"strategy": "newchild_set_type", "candidate": "RGIBBS"},
                ]
            },
        },
    )

    with patch("aspen_automation.session.build_flowsheet_via_com", side_effect=build_error):
        with pytest.raises(BuildError, match="unable to create block 'B-ATR'") as exc_info:
            run_simulation_session(spec, build_mode="auto", output_dir=output_dir)

    assert exc_info.value.mechanism_tried == "com_block_builder"
    assert exc_info.value.diagnostics["block_creation_attempts"]["B-ATR"][0]["strategy"] == "elements_add"


# Case 6: auto path does not generate INP as part of the default build
@patch("aspen_automation.session.generate_inp")
@patch("aspen_automation.session.win32")
def test_06_auto_does_not_generate_inp(mock_win32, mock_gen, spec, output_dir, mock_aspen):
    _mock_dispatch(mock_win32, mock_aspen)

    with patch("aspen_automation.session.build_flowsheet_via_com", return_value=_builder_success()):
        run_simulation_session(spec, build_mode="auto", output_dir=output_dir)

    mock_gen.assert_not_called()


@patch("aspen_automation.session.generate_inp")
@patch("aspen_automation.session.win32")
def test_com_auto_inp_failure_preserves_empty_tree_and_initfromfile_diagnostics(
    mock_win32, mock_gen, spec, output_dir
):
    aspen = MagicMock()
    aspen.Version = "40.0"
    aspen.Engine.IsRunning = False
    worker_diagnostics = {
        "generated_inp_path": "temp_simulation.inp",
        "generated_inp_file": {"path": "temp_simulation.inp", "exists": False, "size_bytes": None},
        "flowsheet_verification": {
            "build_valid": False,
            "stream_count": 0,
            "block_count": 0,
            "stream_samples": [],
            "block_samples": [],
        },
            "import_attempts": [
                {"mechanism": "Import", "path_variant": "raw_string", "success": False, "error": "empty tree"},
                {"mechanism": "Data.Import", "path_variant": "raw_string", "success": False, "error": "empty tree"},
                {"mechanism": "ImportSimulation", "path_variant": "raw_string", "success": False, "error": "empty tree"},
                {
                    "mechanism": "InitFromFile2",
                    "path_variant": "raw_string",
                "success": False,
                "error": "Unable to open file",
            },
        ],
        "InitFromFile2_error": "Unable to open file",
    }
    build_error = BuildError(
        "Aspen import did not materialize a usable flowsheet. Last error: Unable to open file",
        build_mode="auto",
        mechanism_tried="isolated_inp_import_worker",
        diagnostics=worker_diagnostics,
    )
    active_error = BuildError(
        "active fallback failed",
        build_mode="auto",
        mechanism_tried="active_session_import",
        diagnostics={"import_attempts": [{"mechanism": "Import", "success": False, "error": "active fail"}]},
    )
    _mock_dispatch(mock_win32, aspen)

    with patch("aspen_automation.session._build_inp_archive_with_worker", side_effect=build_error), patch(
        "aspen_automation.session._import_file_with_verification",
        side_effect=active_error,
    ):
        with pytest.raises(BuildError, match="Unable to open file") as exc_info:
            run_simulation_session(spec, build_mode="com-auto", output_dir=output_dir)

    diagnostics = exc_info.value.diagnostics
    assert diagnostics["InitFromFile2_error"] == "Unable to open file"
    assert diagnostics["aspen_preflight"]["v14_verified"] is True
    assert diagnostics["generated_inp_path"].endswith("temp_simulation.inp")
    assert diagnostics["generated_inp_file"]["exists"] is False

    initial_import = diagnostics["initial_import_diagnostics"]
    assert initial_import["generated_inp_file"]["exists"] is False
    assert initial_import["flowsheet_verification"]["stream_count"] == 0
    assert initial_import["flowsheet_verification"]["block_count"] == 0
    assert {attempt["mechanism"] for attempt in initial_import["import_attempts"]} >= {
        "Import",
        "Data.Import",
        "ImportSimulation",
    }


@patch("aspen_automation.session.time.sleep", side_effect=None)
def test_import_with_verification_uses_v14_seed_file_fallback(mock_sleep):
    test_root = Path(__file__).resolve().parents[1] / "test_results" / f"v14_seed_{uuid.uuid4().hex}"
    test_root.mkdir(parents=True, exist_ok=False)
    try:
        seed_path = test_root / "testprob.bkp"
        seed_path.write_text("seed", encoding="utf-8")

        state = {"seed_loaded": False, "populated": False}
        data_node = _mock_node()
        aspen = MagicMock()
        aspen.Version = "40.0"

        def _find_node(path):
            if path == r"\Data":
                return data_node
            if path == r"\Data\Streams":
                return _mock_node(names=["S1"] if state["populated"] else [])
            if path == r"\Data\Blocks":
                return _mock_node(names=["B1"] if state["populated"] else [])
            return _mock_node()

        def _import(_path):
            if state["seed_loaded"]:
                state["populated"] = True

        aspen.Tree.FindNode.side_effect = _find_node
        aspen.Import.side_effect = _import
        data_node.Import.return_value = None
        aspen.ImportSimulation.return_value = None
        aspen.InitFromArchive2.side_effect = lambda _path: state.update(seed_loaded=True)

        with patch(
            "aspen_automation.session.ASPEN_V14_SEED_FILE_CANDIDATES",
            (str(seed_path),),
        ):
            diagnostics = _import_file_with_verification(
                aspen,
                str(test_root / "generated.inp"),
                build_mode="auto",
                settle_seconds=0,
            )

        assert diagnostics["build_valid"] is True
        assert diagnostics["build_mechanism"] == "InitFromArchive2+Import"
        assert diagnostics["initialization_source_path"] == str(seed_path)
        assert diagnostics["flowsheet_verification"]["stream_samples"] == ["S1"]
        assert diagnostics["flowsheet_verification"]["block_samples"] == ["B1"]
    finally:
        shutil.rmtree(test_root, ignore_errors=True)


@patch("aspen_automation.session.generate_inp")
@patch("aspen_automation.session.win32")
def test_com_auto_generation_validation_error_preserves_report(mock_win32, mock_gen, spec, output_dir, mock_aspen):
    _mock_dispatch(mock_win32, mock_aspen)
    report = {
        "valid": False,
        "errors": [{"line": 10, "message": "Composition line missing '/' terminator"}],
    }
    mock_gen.side_effect = ValidationError("Generated INP failed validation", report)

    with pytest.raises(BuildError, match="INP generation failed validation") as exc_info:
        run_simulation_session(spec, build_mode="com-auto", output_dir=output_dir)

    assert exc_info.value.mechanism_tried == "generate_inp"
    assert exc_info.value.diagnostics["inp_validation_report"] == report
    assert "generated_inp_path" not in exc_info.value.diagnostics


# Case 7: Converged status
@patch("aspen_automation.session.win32")
def test_07_converged_status(mock_win32, spec, output_dir, mock_aspen):
    _mock_dispatch(mock_win32, mock_aspen)
    # PER_ERROR is 0 by default in mock_aspen fixture

    result = run_simulation_session(spec, build_mode="com-only", output_dir=output_dir)
    assert result.convergence_status == "converged"


# Case 8: Failed status (via PER_ERROR)
@patch("aspen_automation.session.win32")
def test_08_failed_status(mock_win32, spec, output_dir, mock_aspen):
    _mock_dispatch(mock_win32, mock_aspen)
    mock_aspen.Tree.FindNode.return_value.Value = 2  # Error

    result = run_simulation_session(spec, build_mode="com-only", output_dir=output_dir)
    assert result.convergence_status == "failed"


# Case 9: Timeout status
@patch("aspen_automation.session.win32")
@patch("aspen_automation.session.time.sleep", side_effect=None)
@patch("aspen_automation.session.time.time")
def test_09_timeout_status(mock_time, mock_sleep, mock_win32, spec, output_dir, mock_aspen):
    _mock_dispatch(mock_win32, mock_aspen)
    # Forces a timeout (> 300)
    mock_time.side_effect = [0, 5, 10, 311, 312, 313]
    mock_aspen.Engine.IsRunning = True

    result = run_simulation_session(spec, build_mode="com-only", output_dir=output_dir, timeout_seconds=300)

    assert result.convergence_status == "timeout"
    mock_aspen.Engine.Stop.assert_called()


# Case 10: IsRunning check logic coverage
@patch("aspen_automation.session.win32")
@patch("aspen_automation.session.time.sleep", side_effect=None)
@patch("aspen_automation.session.time.time")
def test_10_is_running_logic(mock_time, mock_sleep, mock_win32, spec, output_dir, mock_aspen):
    _mock_dispatch(mock_win32, mock_aspen)
    mock_time.side_effect = [0, 10, 11, 12, 13]  # Advance time slowly

    # True then False
    type(mock_aspen.Engine).IsRunning = PropertyMock(side_effect=[True, True, False])
    mock_time.side_effect = range(100) # Plenty of timestamps

    run_simulation_session(spec, build_mode="com-only", output_dir=output_dir)

    # Verify sleep called
    assert mock_sleep.called
    assert mock_sleep.call_count == 2


# Case 11: Cleanup removes artifacts
@patch("aspen_automation.session.win32")
@patch("aspen_automation.session.os.remove")
@patch("aspen_automation.session.os.listdir")
@patch("aspen_automation.session.os.path.exists")
def test_11_cleanup(mock_exists, mock_listdir, mock_remove, mock_win32, spec, output_dir, mock_aspen):
    _mock_dispatch(mock_win32, mock_aspen)
    mock_exists.return_value = True
    mock_listdir.return_value = ["test.bkp", "test.inp", "keep.txt"]

    run_simulation_session(spec, build_mode="com-only", output_dir=output_dir, keep_alive=False)

    mock_aspen.Quit.assert_called()
    assert mock_remove.called


# Case 12: Visibility flag honored
@patch("aspen_automation.session.generate_inp")
@patch("aspen_automation.session.win32")
def test_12_visibility(mock_win32, mock_gen, spec, output_dir):
    mock_aspen_local = MagicMock()
    mock_aspen_local.Version = "40.0"
    mock_aspen_local.Engine.IsRunning = False
    mock_node = MagicMock()
    mock_node.Value = 0
    mock_aspen_local.Tree.FindNode.return_value = mock_node
    _mock_dispatch(mock_win32, mock_aspen_local)

    run_simulation_session(spec, build_mode="com-only", visible=False, output_dir=output_dir)
    # Check property setting on the mock
    assert mock_aspen_local.Visible == 0

    run_simulation_session(spec, build_mode="com-only", visible=True, output_dir=output_dir)
    assert mock_aspen_local.Visible == 1


# Case 13: Invalid build_mode raises ValueError
def test_13_invalid_mode(spec, output_dir):
    with pytest.raises(ValueError):
        run_simulation_session(spec, build_mode="invalid", output_dir=output_dir)


# ---------------------------------------------------------------------------
# Comment 3: _verify_flowsheet
# ---------------------------------------------------------------------------

def test_verify_flowsheet_passes_when_both_nodes_present():
    """Should not raise when \\Data\\Streams node is found."""
    aspen = MagicMock()
    aspen.Tree.FindNode.side_effect = [MagicMock(), MagicMock()]
    _verify_flowsheet(aspen)  # must not raise
    assert aspen.Tree.FindNode.call_count == 2


def test_verify_flowsheet_raises_build_error_when_streams_missing():
    """Should raise BuildError when \\Data\\Streams node is None."""
    aspen = MagicMock()
    aspen.Tree.FindNode.return_value = None
    with pytest.raises(BuildError, match="Streams"):
        _verify_flowsheet(aspen)


def test_verify_flowsheet_raises_build_error_when_blocks_missing():
    """Should raise BuildError when \\Data\\Blocks node is None."""
    aspen = MagicMock()
    aspen.Tree.FindNode.side_effect = [MagicMock(), None]
    with pytest.raises(BuildError, match="Blocks"):
        _verify_flowsheet(aspen)


# ---------------------------------------------------------------------------
# Comment 1: spec type branching in run_simulation_session
# ---------------------------------------------------------------------------

@patch("aspen_automation.session.generate_inp")
@patch("aspen_automation.session.win32")
@patch("aspen_automation.session.load_spec")
def test_spec_str_calls_load_spec(mock_load, mock_win32, mock_gen, output_dir, mock_aspen):
    """Passing a str spec should delegate to load_spec."""
    _mock_dispatch(mock_win32, mock_aspen)
    expected_spec = MagicMock(spec=PlantSpecification)
    mock_load.return_value = expected_spec

    run_simulation_session("path/to/spec.yaml", build_mode="com-only", output_dir=output_dir)

    mock_load.assert_called_once_with("path/to/spec.yaml")


@patch("aspen_automation.session.generate_inp")
@patch("aspen_automation.session.win32")
@patch("aspen_automation.session.validate_spec")
def test_spec_dict_calls_validate_spec(mock_validate, mock_win32, mock_gen, spec, output_dir, mock_aspen):
    """Passing a dict spec should call validate_spec; invalid dict raises ValueError."""
    _mock_dispatch(mock_win32, mock_aspen)
    mock_validate.return_value = {"valid": False, "errors": [{"message": "bad"}]}

    with pytest.raises(ValueError, match="Invalid spec dict"):
        run_simulation_session(spec.model_dump(), build_mode="com-only", output_dir=output_dir)


@patch("aspen_automation.session.win32")
@patch("aspen_automation.session.validate_spec")
def test_spec_plant_specification_validates(mock_validate, mock_win32, spec, output_dir, mock_aspen):
    """PlantSpecification instances should also be validated; invalid spec raises ValueError."""
    _mock_dispatch(mock_win32, mock_aspen)
    mock_validate.return_value = {"valid": False, "errors": [{"message": "bad"}]}

    with pytest.raises(ValueError, match="Invalid PlantSpecification"):
        run_simulation_session(spec, build_mode="com-only", output_dir=output_dir)


@patch("aspen_automation.session.win32")
def test_run_session_continues_when_preflight_version_is_unreported(
    mock_win32, spec, output_dir, mock_aspen
):
    mock_aspen.Version = None
    mock_aspen.Application = object()
    _mock_dispatch(mock_win32, mock_aspen)

    result = run_simulation_session(spec, build_mode="com-only", output_dir=output_dir)

    assert result.convergence_status == "converged"
    assert result.diagnostics["aspen_connection_verified"] is True
    assert result.diagnostics["v14_version_verified"] is False
    assert result.diagnostics["aspen_preflight"]["version_status"] == "unreported"
    assert result.diagnostics["aspen_preflight"]["preflight_status"] == "connected_version_unreported"


@patch("aspen_automation.session.win32")
def test_run_session_soft_fails_wrong_reported_version_with_preflight_diagnostics(
    mock_win32, spec, output_dir, mock_aspen
):
    mock_aspen.Version = "39.0"
    _mock_dispatch(mock_win32, mock_aspen)

    result = run_simulation_session(spec, build_mode="com-only", output_dir=output_dir)

    assert result.convergence_status == "failed"
    assert result.aspen is None
    assert result.diagnostics["connection_error_type"] == "AspenConnectionError"
    assert result.diagnostics["aspen_preflight"]["version_status"] == "wrong_version"
    assert result.diagnostics["aspen_preflight"]["preflight_status"] == "wrong_version"


@patch("aspen_automation.session.win32")
def test_connection_error_soft_fail(mock_win32, spec, output_dir):
    _mock_dispatch_error(mock_win32, AspenConnectionError("Cannot connect"))

    result = run_simulation_session(
        spec,
        build_mode="com-only",
        output_dir=output_dir,
        raise_on_connection_error=False,
    )

    assert result.convergence_status == "failed"
    assert "error" in result.diagnostics


@patch("aspen_automation.session.win32")
def test_connection_error_raises(mock_win32, spec, output_dir):
    _mock_dispatch_error(mock_win32, AspenConnectionError("Cannot connect"))

    with pytest.raises(AspenConnectionError):
        run_simulation_session(
            spec,
            build_mode="com-only",
            output_dir=output_dir,
            raise_on_connection_error=True,
        )


@patch("aspen_automation.session.generate_inp")
@patch("aspen_automation.session.win32")
@patch("aspen_automation.session._cleanup_session")
def test_cleanup_forced_on_raised_error_with_keep_alive(
    mock_cleanup, mock_win32, mock_gen, spec, output_dir, mock_aspen
):
    _mock_dispatch(mock_win32, mock_aspen)
    mock_aspen.InitFromFile2.side_effect = Exception("Init failed")

    with pytest.raises(BuildError, match="Init failed"):
        run_simulation_session(
            spec,
            build_mode="inp-only",
            output_dir=output_dir,
            keep_alive=True,
        )

    args = mock_cleanup.call_args.args
    assert args[0] is mock_aspen
    assert args[1] == output_dir
    assert args[2].endswith("temp_simulation.inp")
    assert args[3] is False


@patch("aspen_automation.session.win32")
@patch("aspen_automation.session._cleanup_session")
def test_cleanup_forced_on_connection_error_raise_with_keep_alive(
    mock_cleanup, mock_win32, spec, output_dir
):
    _mock_dispatch_error(mock_win32, AspenConnectionError("Cannot connect"))

    with pytest.raises(AspenConnectionError):
        run_simulation_session(
            spec,
            build_mode="com-only",
            output_dir=output_dir,
            keep_alive=True,
            raise_on_connection_error=True,
        )

    args = mock_cleanup.call_args.args
    assert args[0] is None
    assert args[1] == output_dir
    assert args[2].endswith("temp_simulation.inp")
    assert args[3] is False


# ---------------------------------------------------------------------------
# PR-1 runtime correctness: new tests (RED — must fail before fixes applied)
# ---------------------------------------------------------------------------

@patch("aspen_automation.session.time.sleep", side_effect=None)
@patch("aspen_automation.session.time.time")
def test_simulation_polling_does_not_exit_immediately_when_both_running_props_raise(
    mock_time, mock_sleep
):
    """When both EngineRunning and Engine.IsRunning raise on the first tick, the
    polling loop must NOT break immediately.  Doing so would return a stale
    convergence status before the engine has done any work.

    Fix: treat None (ambiguous) differently from False (explicit stop signal).
    """
    mock_time.side_effect = iter(range(1000))

    aspen = MagicMock()
    engine = MagicMock()
    aspen.Engine = engine

    # EngineRunning always raises — property not available on this Aspen build
    type(aspen).EngineRunning = PropertyMock(side_effect=AttributeError("EngineRunning not available"))

    # Engine.IsRunning: raises on first access (tick 1), returns False on second (tick 2)
    type(engine).IsRunning = PropertyMock(
        side_effect=[AttributeError("IsRunning not available"), False]
    )

    mock_node = MagicMock()
    mock_node.Value = 0  # PER_ERROR = 0 → converged
    aspen.Tree.FindNode.return_value = mock_node

    status, _elapsed, _messages, _diag = _run_simulation(aspen, timeout=300)

    # If the loop broke on tick 1 (bug), sleep is never called.
    # After the fix, the loop runs tick 1 (sleeps) then exits on tick 2.
    assert mock_sleep.call_count >= 1, (
        f"Polling loop exited immediately on ambiguous COM state "
        f"(time.sleep called {mock_sleep.call_count} times, expected ≥ 1)"
    )
    assert status == "converged"


def test_com_only_raises_build_error_when_init_new_fails(spec):
    """_build_com_only must raise BuildError when InitNew() fails.

    Currently the exception is silently swallowed, so _run_simulation then
    operates on an uninitialised document.
    """
    aspen = MagicMock()
    aspen.InitNew.side_effect = RuntimeError("COM InitNew failed")
    result = SessionResult()

    with pytest.raises(BuildError, match="COM InitNew failed"):
        _build_com_only(spec, aspen, result)


def test_cleanup_session_deletes_temp_inp_when_keep_alive_false():
    """_cleanup_session must delete the temp INP file when keep_alive=False.

    The os.remove() call was commented out, causing INP files to accumulate
    in the output directory across runs.
    """
    import tempfile, os as _os
    with tempfile.TemporaryDirectory() as tmpdir:
        inp_path = _os.path.join(tmpdir, "temp_simulation.inp")
        with open(inp_path, "w", encoding="utf-8") as f:
            f.write("TITLE 'Test'")

        assert _os.path.exists(inp_path), "precondition: file must exist before cleanup"

        _cleanup_session(None, tmpdir, inp_path, keep_alive=False)

        assert not _os.path.exists(inp_path), "INP file must be removed after cleanup"

