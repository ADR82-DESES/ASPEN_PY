# AppsAnywhere Pre-flight Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `check_aspen_running()` guard that raises a clear `AspenNotRunningError` when Aspen Plus is not running, replacing the cryptic COM localization error users get when running the codebase without first launching Aspen from the Porticada portal.

**Architecture:** New `AspenNotRunningError` exception subclasses `AspenConnectionError` so existing catch blocks are unaffected. A `check_aspen_running()` function uses `win32.GetActiveObject` (read-only, never launches Aspen) and is injected at the top of `run_simulation_session()` before any COM interaction. A matching pre-flight cell in the notebook surfaces the error at the start of a notebook run rather than after a long wait in cell 9.

**Tech Stack:** Python 3.12, pywin32 (`win32com.client`), pytest with `unittest.mock`, Jupyter notebooks (`.ipynb` JSON format)

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `aspen_automation/exceptions.py` | Modify | Add `AspenNotRunningError` |
| `aspen_automation/session.py` | Modify | Add `check_aspen_running()` + guard in `run_simulation_session()` |
| `aspen_automation/__init__.py` | Modify | Export new symbols |
| `notebooks/process_library_runner.ipynb` | Modify | Insert pre-flight cell between sections 1 and 2 |
| `tests/test_session.py` | Modify | Tests for `check_aspen_running()` and the guard |

---

## Task 1: Add `AspenNotRunningError` to `exceptions.py`

**Files:**
- Modify: `aspen_automation/exceptions.py`
- Test: `tests/test_session.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_session.py` (after the existing imports, before the fixtures):

```python
from aspen_automation.exceptions import AspenNotRunningError

def test_aspen_not_running_error_is_connection_error():
    err = AspenNotRunningError()
    assert isinstance(err, AspenConnectionError)

def test_aspen_not_running_error_message_contains_portal():
    err = AspenNotRunningError()
    assert "Porticada" in str(err)
    assert "porticada.unican.es" in str(err)

def test_aspen_not_running_error_takes_no_args():
    # Should construct with zero arguments
    err = AspenNotRunningError()
    assert err is not None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd c:/Users/domingueza/ASPEN_PY
pixi run pytest tests/test_session.py::test_aspen_not_running_error_is_connection_error tests/test_session.py::test_aspen_not_running_error_message_contains_portal tests/test_session.py::test_aspen_not_running_error_takes_no_args -v
```

Expected: `ImportError` or `FAILED` — `AspenNotRunningError` does not exist yet.

- [ ] **Step 3: Add `AspenNotRunningError` to `exceptions.py`**

Open `aspen_automation/exceptions.py`. After the `AspenConnectionError` class (currently ends at line 25), add:

```python
class AspenNotRunningError(AspenConnectionError):
    def __init__(self):
        super().__init__(
            "Aspen Plus is not running. "
            "Please launch Aspen 14 from the Porticada portal "
            "(https://porticada.unican.es) and try again."
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pixi run pytest tests/test_session.py::test_aspen_not_running_error_is_connection_error tests/test_session.py::test_aspen_not_running_error_message_contains_portal tests/test_session.py::test_aspen_not_running_error_takes_no_args -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add aspen_automation/exceptions.py tests/test_session.py
git commit -m "feat: add AspenNotRunningError exception"
```

---

## Task 2: Add `check_aspen_running()` to `session.py`

**Files:**
- Modify: `aspen_automation/session.py`
- Test: `tests/test_session.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_session.py` (after the Task 1 tests):

```python
from aspen_automation.session import check_aspen_running

def test_check_aspen_running_returns_false_when_win32_unavailable():
    with patch("aspen_automation.session.win32", None):
        assert check_aspen_running() is False

def test_check_aspen_running_returns_true_when_active_object_succeeds():
    mock_win32 = MagicMock()
    mock_win32.GetActiveObject.return_value = MagicMock()
    with patch("aspen_automation.session.win32", mock_win32):
        assert check_aspen_running() is True
    mock_win32.GetActiveObject.assert_called_once_with("Apwn.Document")

def test_check_aspen_running_returns_false_when_active_object_raises():
    mock_win32 = MagicMock()
    mock_win32.GetActiveObject.side_effect = Exception("not running")
    with patch("aspen_automation.session.win32", mock_win32):
        assert check_aspen_running() is False

def test_check_aspen_running_never_raises():
    mock_win32 = MagicMock()
    mock_win32.GetActiveObject.side_effect = RuntimeError("catastrophic")
    with patch("aspen_automation.session.win32", mock_win32):
        result = check_aspen_running()  # must not raise
    assert result is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pixi run pytest tests/test_session.py::test_check_aspen_running_returns_false_when_win32_unavailable tests/test_session.py::test_check_aspen_running_returns_true_when_active_object_succeeds tests/test_session.py::test_check_aspen_running_returns_false_when_active_object_raises tests/test_session.py::test_check_aspen_running_never_raises -v
```

Expected: `ImportError` or `FAILED` — `check_aspen_running` does not exist yet.

- [ ] **Step 3: Add `check_aspen_running()` to `session.py`**

Open `aspen_automation/session.py`. Add the function immediately after the `_connect_aspen()` function definition (currently ends around line 333). Place it before `_node_summary()`:

```python
def check_aspen_running() -> bool:
    """Returns True if Aspen Plus is currently running and reachable via COM."""
    if win32 is None:
        return False
    try:
        win32.GetActiveObject(ASPEN_DOCUMENT_PROG_ID)
        return True
    except Exception:
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pixi run pytest tests/test_session.py::test_check_aspen_running_returns_false_when_win32_unavailable tests/test_session.py::test_check_aspen_running_returns_true_when_active_object_succeeds tests/test_session.py::test_check_aspen_running_returns_false_when_active_object_raises tests/test_session.py::test_check_aspen_running_never_raises -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add aspen_automation/session.py tests/test_session.py
git commit -m "feat: add check_aspen_running() utility function"
```

---

## Task 3: Inject the guard into `run_simulation_session()`

**Files:**
- Modify: `aspen_automation/session.py`
- Test: `tests/test_session.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_session.py`:

```python
def test_run_simulation_session_raises_when_aspen_not_running(spec, output_dir):
    with patch("aspen_automation.session.check_aspen_running", return_value=False):
        with pytest.raises(AspenNotRunningError):
            run_simulation_session(spec, output_dir=output_dir)

def test_run_simulation_session_proceeds_when_aspen_running(spec, output_dir):
    mock_aspen = MagicMock()
    with patch("aspen_automation.session.check_aspen_running", return_value=True), \
         patch("aspen_automation.session._connect_aspen", return_value=mock_aspen), \
         patch("aspen_automation.session._verify_aspen_v14_connection", return_value={"connection_verified": True, "v14_verified": True, "v14_version_verified": True, "aspen_version": "40.0"}), \
         patch("aspen_automation.session._build_auto", return_value={"status": "built", "mechanism": "com", "fallback_attempted": False, "diagnostics": {}}), \
         patch("aspen_automation.session._run_simulation", return_value="converged"), \
         patch("aspen_automation.session._cleanup_session"):
        result = run_simulation_session(spec, output_dir=output_dir)
    assert result.convergence_status == "converged"

def test_run_simulation_session_not_running_error_is_connection_error(spec, output_dir):
    # Verify AspenNotRunningError is catchable as AspenConnectionError
    with patch("aspen_automation.session.check_aspen_running", return_value=False):
        with pytest.raises(AspenConnectionError):
            run_simulation_session(spec, output_dir=output_dir)
```

Also add `AspenNotRunningError` to the imports at the top of `tests/test_session.py`:

```python
from aspen_automation.exceptions import ValidationError, AspenNotRunningError
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pixi run pytest tests/test_session.py::test_run_simulation_session_raises_when_aspen_not_running tests/test_session.py::test_run_simulation_session_proceeds_when_aspen_running tests/test_session.py::test_run_simulation_session_not_running_error_is_connection_error -v
```

Expected: `FAILED` — the guard does not exist yet so the first test will not raise `AspenNotRunningError`.

- [ ] **Step 3: Inject the guard in `run_simulation_session()`**

Open `aspen_automation/session.py`. Find the `try:` block inside `run_simulation_session()` (around line 1598). The block begins with:

```python
    aspen = None
    force_cleanup = False
    try:
        # Connect
        aspen = _connect_aspen()
```

Add the guard as the **first two lines** inside the `try:` block, before `aspen = _connect_aspen()`:

```python
    aspen = None
    force_cleanup = False
    try:
        if not check_aspen_running():
            raise AspenNotRunningError()
        # Connect
        aspen = _connect_aspen()
```

Also add `AspenNotRunningError` to the import at the top of `session.py`. Find:

```python
from .exceptions import AspenConnectionError, BuildError, SimulationError, ValidationError
```

Replace with:

```python
from .exceptions import AspenConnectionError, AspenNotRunningError, BuildError, SimulationError, ValidationError
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pixi run pytest tests/test_session.py::test_run_simulation_session_raises_when_aspen_not_running tests/test_session.py::test_run_simulation_session_proceeds_when_aspen_running tests/test_session.py::test_run_simulation_session_not_running_error_is_connection_error -v
```

Expected: `3 passed`

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
pixi run pytest tests/test_session.py -v
```

Expected: all previously passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add aspen_automation/session.py tests/test_session.py
git commit -m "feat: inject AspenNotRunningError guard into run_simulation_session"
```

---

## Task 4: Export new symbols and add notebook pre-flight cell

**Files:**
- Modify: `aspen_automation/__init__.py`
- Modify: `notebooks/process_library_runner.ipynb`

- [ ] **Step 1: Update `__init__.py` exports**

Open `aspen_automation/__init__.py`. Find line 4:

```python
from .exceptions import ValidationError, ParserError, SchemaError, ExtractionError, AspenConnectionError, BuildError, SimulationError
```

Replace with:

```python
from .exceptions import ValidationError, ParserError, SchemaError, ExtractionError, AspenConnectionError, AspenNotRunningError, BuildError, SimulationError
```

Find line 15:

```python
from .session import check_aspen_v14_connection, run_simulation_session, SessionResult
```

Replace with:

```python
from .session import check_aspen_running, check_aspen_v14_connection, run_simulation_session, SessionResult
```

- [ ] **Step 2: Verify the exports are importable**

```bash
pixi run python -c "from aspen_automation import check_aspen_running; from aspen_automation.exceptions import AspenNotRunningError; print('OK')"
```

Expected output: `OK`

- [ ] **Step 3: Insert the pre-flight cell into the notebook**

Open `notebooks/process_library_runner.ipynb` in a text editor. The file is JSON. Find the cell with `"id": "361361dd"` — this is the `## 1. Environment setup and imports` markdown cell. The **next** cell after it (id `feb1db5b`) contains the Python imports.

Insert two new cells **after** `feb1db5b` (the imports cell) and **before** `d80e2500` (the `## 2. Repository path resolution` markdown cell).

The two cells to insert are:

**Markdown cell** (insert first):
```json
{
 "cell_type": "markdown",
 "id": "preflight-header",
 "metadata": {},
 "source": [
  "## 1.5 Aspen Plus pre-flight check"
 ]
}
```

**Code cell** (insert second):
```json
{
 "cell_type": "code",
 "execution_count": null,
 "id": "preflight-check",
 "metadata": {},
 "outputs": [],
 "source": [
  "from aspen_automation import check_aspen_running\n",
  "from aspen_automation.exceptions import AspenNotRunningError\n",
  "\n",
  "if not check_aspen_running():\n",
  "    raise AspenNotRunningError()\n",
  "\n",
  "print('Aspen Plus is running. Ready to proceed.')"
 ]
}
```

In the notebook JSON the `"cells"` array looks like:
```
[..., <cell id feb1db5b>, <cell id d80e2500>, ...]
```

After the edit it should look like:
```
[..., <cell id feb1db5b>, <markdown preflight-header>, <code preflight-check>, <cell id d80e2500>, ...]
```

- [ ] **Step 4: Validate the notebook is valid JSON**

```bash
pixi run python -c "import json; json.load(open('notebooks/process_library_runner.ipynb')); print('Valid JSON')"
```

Expected output: `Valid JSON`

- [ ] **Step 5: Run the full test suite one final time**

```bash
pixi run pytest tests/ -v --ignore=tests/integration -q
```

Expected: all tests pass (same count as before this feature).

- [ ] **Step 6: Final commit**

```bash
git add aspen_automation/__init__.py notebooks/process_library_runner.ipynb
git commit -m "feat: export check_aspen_running and add notebook pre-flight cell"
```

---

## Verification

After all tasks are complete, with Aspen **not** running:

```bash
pixi run python -c "
from aspen_automation import run_simulation_session, load_spec
try:
    run_simulation_session('templates/minimal_test.yaml')
except Exception as e:
    print(type(e).__name__, ':', e)
"
```

Expected output:
```
AspenNotRunningError : Aspen Plus is not running. Please launch Aspen 14 from the Porticada portal (https://porticada.unican.es) and try again.
```
