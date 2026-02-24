import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import sys

# Mock win32com before import
sys.modules["win32com"] = MagicMock()
sys.modules["win32com.client"] = MagicMock()

from aspen_automation.session import (
    run_simulation_session,
    SessionResult,
    AspenConnectionError,
    BuildError,
    SimulationError,
    _connect_aspen,
    _build_inp_only,
    _build_com_only,
    _build_auto,
    _run_simulation,
    _verify_flowsheet,
)
from aspen_automation.schema import PlantSpecification, Metadata, UnitSystem, Properties


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


@pytest.fixture
def mock_aspen():
    aspen = MagicMock()
    aspen.Engine.IsRunning = False
    mock_node = MagicMock()
    mock_node.Value = 0
    aspen.Tree.FindNode.return_value = mock_node
    return aspen


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

# Case 1: inp-only success
@patch("aspen_automation.session.generate_inp")
@patch("aspen_automation.session.win32")
def test_01_inp_only_success(mock_win32, mock_gen, spec, output_dir, mock_aspen):
    mock_win32.Dispatch.return_value = mock_aspen

    result = run_simulation_session(spec, build_mode="inp-only", output_dir=output_dir)

    assert result.build_mode == "inp-only"
    assert result.build_mechanism_used == "InitFromFile2"
    mock_aspen.InitFromFile2.assert_called()
    assert result.convergence_status == "converged"


# Case 2: inp-only fail raises BuildError (Comment 2)
@patch("aspen_automation.session.generate_inp")
@patch("aspen_automation.session.win32")
def test_02_inp_only_fail(mock_win32, mock_gen, spec, output_dir, mock_aspen):
    mock_win32.Dispatch.return_value = mock_aspen
    mock_aspen.InitFromFile2.side_effect = Exception("Init failed")

    with pytest.raises(BuildError, match="Init failed"):
        run_simulation_session(spec, build_mode="inp-only", output_dir=output_dir)


# Case 3: com-only diagnostic success
@patch("aspen_automation.session.win32")
def test_03_com_only_diagnostic(mock_win32, spec, output_dir, mock_aspen):
    mock_win32.Dispatch.return_value = mock_aspen

    result = run_simulation_session(spec, build_mode="com-only", output_dir=output_dir)

    assert result.build_mode == "com-only"
    assert result.build_mechanism_used == "COM"
    mock_aspen.InitNew.assert_called()
    assert "warning" in result.diagnostics


# Case 4: auto primary success
@patch("aspen_automation.session.generate_inp")
@patch("aspen_automation.session.win32")
def test_04_auto_primary_success(mock_win32, mock_gen, spec, output_dir, mock_aspen):
    mock_win32.Dispatch.return_value = mock_aspen

    result = run_simulation_session(spec, build_mode="auto", output_dir=output_dir)

    assert result.build_mode == "auto"
    assert result.build_mechanism_used == "InitFromFile2"
    assert not result.build_fallback_attempted
    mock_aspen.InitFromFile2.assert_called()


# Case 5: auto fallback success
@patch("aspen_automation.session.generate_inp")
@patch("aspen_automation.session.win32")
def test_05_auto_fallback_success(mock_win32, mock_gen, spec, output_dir, mock_aspen):
    mock_win32.Dispatch.return_value = mock_aspen
    mock_aspen.InitFromFile2.side_effect = Exception("File fail")

    result = run_simulation_session(spec, build_mode="auto", output_dir=output_dir)

    assert result.build_mode == "auto"
    assert result.build_mechanism_used == "Import"
    assert result.build_fallback_attempted
    mock_aspen.InitFromFile2.assert_called()
    mock_aspen.InitNew.assert_called()
    mock_aspen.Import.assert_called()


# Case 6: auto both fail raises BuildError (Comment 2)
@patch("aspen_automation.session.generate_inp")
@patch("aspen_automation.session.win32")
def test_06_auto_both_fail(mock_win32, mock_gen, spec, output_dir, mock_aspen):
    mock_win32.Dispatch.return_value = mock_aspen
    mock_aspen.InitFromFile2.side_effect = Exception("File fail")
    mock_aspen.Import.side_effect = AttributeError("Import missing")
    mock_aspen.ImportSimulation.side_effect = Exception("Import fail")

    with pytest.raises(BuildError, match="Import fail"):
        run_simulation_session(spec, build_mode="auto", output_dir=output_dir)


# Case 7: Converged status
@patch("aspen_automation.session.win32")
def test_07_converged_status(mock_win32, spec, output_dir, mock_aspen):
    mock_win32.Dispatch.return_value = mock_aspen
    # PER_ERROR is 0 by default in mock_aspen fixture

    result = run_simulation_session(spec, build_mode="com-only", output_dir=output_dir)
    assert result.convergence_status == "converged"


# Case 8: Failed status (via PER_ERROR)
@patch("aspen_automation.session.win32")
def test_08_failed_status(mock_win32, spec, output_dir, mock_aspen):
    mock_win32.Dispatch.return_value = mock_aspen
    mock_aspen.Tree.FindNode.return_value.Value = 2  # Error

    result = run_simulation_session(spec, build_mode="com-only", output_dir=output_dir)
    assert result.convergence_status == "failed"


# Case 9: Timeout status
@patch("aspen_automation.session.win32")
@patch("aspen_automation.session.time.sleep", side_effect=None)
@patch("aspen_automation.session.time.time")
def test_09_timeout_status(mock_time, mock_sleep, mock_win32, spec, output_dir, mock_aspen):
    mock_win32.Dispatch.return_value = mock_aspen
    mock_aspen.Engine.IsRunning = True  # Keep running
    mock_time.side_effect = [0, 10, 311]  # Advance to trigger timeout > 300

    result = run_simulation_session(spec, build_mode="com-only", output_dir=output_dir, timeout_seconds=300)

    assert result.convergence_status == "timeout"
    mock_aspen.Engine.Stop.assert_called()


# Case 10: IsRunning check logic coverage
@patch("aspen_automation.session.win32")
@patch("aspen_automation.session.time.sleep", side_effect=None)
@patch("aspen_automation.session.time.time")
def test_10_is_running_logic(mock_time, mock_sleep, mock_win32, spec, output_dir, mock_aspen):
    mock_win32.Dispatch.return_value = mock_aspen
    mock_time.side_effect = [0, 10, 11, 12, 13]  # Advance time slowly

    # True then False
    type(mock_aspen.Engine).IsRunning = PropertyMock(side_effect=[True, True, False])

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
    mock_win32.Dispatch.return_value = mock_aspen
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
    mock_aspen_local.Engine.IsRunning = False
    mock_node = MagicMock()
    mock_node.Value = 0
    mock_aspen_local.Tree.FindNode.return_value = mock_node
    mock_win32.Dispatch.return_value = mock_aspen_local

    run_simulation_session(spec, visible=False, output_dir=output_dir)
    assert mock_aspen_local.Visible == 0

    run_simulation_session(spec, visible=True, output_dir=output_dir)
    assert mock_aspen_local.Visible == 1


# Case 13: Invalid build_mode raises ValueError
def test_13_invalid_mode(spec, output_dir):
    with pytest.raises(ValueError):
        run_simulation_session(spec, build_mode="invalid", output_dir=output_dir)


# ---------------------------------------------------------------------------
# Comment 3: _verify_flowsheet
# ---------------------------------------------------------------------------

def test_verify_flowsheet_passes_when_streams_node_present():
    """Should not raise when \\Data\\Streams node is found."""
    aspen = MagicMock()
    aspen.Tree.FindNode.return_value = MagicMock()  # truthy -> present
    _verify_flowsheet(aspen)  # must not raise
    aspen.Tree.FindNode.assert_called_once_with(r"\Data\Streams")


def test_verify_flowsheet_raises_build_error_when_missing():
    """Should raise BuildError when \\Data\\Streams node is None."""
    aspen = MagicMock()
    aspen.Tree.FindNode.return_value = None
    with pytest.raises(BuildError, match="Streams"):
        _verify_flowsheet(aspen)


# ---------------------------------------------------------------------------
# Comment 1: spec type branching in run_simulation_session
# ---------------------------------------------------------------------------

@patch("aspen_automation.session.generate_inp")
@patch("aspen_automation.session.win32")
@patch("aspen_automation.session.load_spec")
def test_spec_str_calls_load_spec(mock_load, mock_win32, mock_gen, output_dir, mock_aspen):
    """Passing a str spec should delegate to load_spec."""
    mock_win32.Dispatch.return_value = mock_aspen
    expected_spec = MagicMock(spec=PlantSpecification)
    mock_load.return_value = expected_spec

    run_simulation_session("path/to/spec.yaml", build_mode="com-only", output_dir=output_dir)

    mock_load.assert_called_once_with("path/to/spec.yaml")


@patch("aspen_automation.session.generate_inp")
@patch("aspen_automation.session.win32")
@patch("aspen_automation.session.validate_spec")
def test_spec_dict_calls_validate_spec(mock_validate, mock_win32, mock_gen, spec, output_dir, mock_aspen):
    """Passing a dict spec should call validate_spec; invalid dict raises ValueError."""
    mock_win32.Dispatch.return_value = mock_aspen
    mock_validate.return_value = {"valid": False, "errors": [{"message": "bad"}]}

    with pytest.raises(ValueError, match="Invalid spec dict"):
        run_simulation_session(spec.model_dump(), build_mode="com-only", output_dir=output_dir)


@patch("aspen_automation.session.win32")
@patch("aspen_automation.session.validate_spec")
def test_spec_plant_specification_validates(mock_validate, mock_win32, spec, output_dir, mock_aspen):
    """PlantSpecification instances should also be validated; invalid spec raises ValueError."""
    mock_win32.Dispatch.return_value = mock_aspen
    mock_validate.return_value = {"valid": False, "errors": [{"message": "bad"}]}

    with pytest.raises(ValueError, match="Invalid PlantSpecification"):
        run_simulation_session(spec, build_mode="com-only", output_dir=output_dir)


@patch("aspen_automation.session.win32")
def test_connection_error_soft_fail(mock_win32, spec, output_dir):
    mock_win32.Dispatch.side_effect = AspenConnectionError("Cannot connect")

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
    mock_win32.Dispatch.side_effect = AspenConnectionError("Cannot connect")

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
    mock_win32.Dispatch.return_value = mock_aspen
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
    mock_win32.Dispatch.side_effect = AspenConnectionError("Cannot connect")

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
