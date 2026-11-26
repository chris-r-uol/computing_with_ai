import shutil
from pathlib import Path

import pytest
from run_notebooks import (
    TIMEOUT_SECONDS,
    NotebookResult,
    main,
    run,
    run_all,
)

REPO = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / "fixtures"


def test_timeout_matches_the_design_ceiling():
    assert TIMEOUT_SECONDS == 120


def test_broken_notebook_is_reported_not_raised():
    result = run(FIXTURES / "broken.ipynb")
    assert not result.passed
    assert "NameError" in result.error


def test_a_tagged_raising_cell_does_not_fail_the_notebook_runner():
    result = run(FIXTURES / "raises_exception.ipynb")
    assert result.passed, result.error


def _write(path, source):
    import nbformat

    nb = nbformat.v4.new_notebook()
    nb.cells = [nbformat.v4.new_code_cell(source)]
    nbformat.write(nb, path)


def test_notebook_depending_on_earlier_state_fails_in_isolation(tmp_path):
    # The first notebook defines the name and runs first (sorted order). If the
    # kernel were shared, the second would find it and pass. It must not.
    _write(tmp_path / "a_defines.ipynb", "earlier_result = 41")
    _write(tmp_path / "b_uses.ipynb", "print(earlier_result + 1)")
    results = {r.path.name: r for r in run_all(tmp_path)}
    assert results["a_defines.ipynb"].passed
    assert not results["b_uses.ipynb"].passed
    assert "earlier_result" in results["b_uses.ipynb"].error


def test_fixture_depending_on_earlier_state_fails():
    result = run(FIXTURES / "depends_on_earlier.ipynb")
    assert not result.passed
    assert "earlier_result" in result.error


def test_smoke_notebook_passes_within_timeout():
    result = run(REPO / "notebooks/01-foundations/00-smoke.ipynb")
    assert result.passed, result.error
    assert result.error is None
    assert result.seconds < TIMEOUT_SECONDS


def test_slow_notebook_is_reported_as_timeout(tmp_path):
    import nbformat

    nb = nbformat.v4.new_notebook()
    nb.cells = [nbformat.v4.new_code_cell("import time; time.sleep(30)")]
    path = tmp_path / "slow.ipynb"
    nbformat.write(nb, path)
    result = run(path, timeout=2)
    assert not result.passed
    assert "Timeout" in result.error


def test_result_is_frozen():
    result = NotebookResult(Path("x"), True, 0.1, None)
    with pytest.raises(AttributeError):
        result.passed = False


def test_run_all_returns_one_result_per_notebook():
    results = run_all(FIXTURES)
    assert len(results) == len(list(FIXTURES.glob("*.ipynb")))
    assert [r.path for r in results] == sorted(r.path for r in results)


def test_run_all_continues_past_a_failure():
    results = {r.path.name: r for r in run_all(FIXTURES)}
    assert not results["broken.ipynb"].passed
    assert not results["depends_on_earlier.ipynb"].passed


def test_run_all_ignores_checkpoint_copies(tmp_path):
    (tmp_path / ".ipynb_checkpoints").mkdir()
    (tmp_path / ".ipynb_checkpoints" / "x-checkpoint.ipynb").write_text("{}")
    assert run_all(tmp_path) == []


def test_main_exits_non_zero_when_any_notebook_fails(capsys):
    assert main([str(FIXTURES)]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_main_exits_zero_when_all_pass(tmp_path, capsys):
    # Only the smoke notebook, so pytest stays independent of course content
    # (later notebooks may need the optional deep-learning group).
    shutil.copy(REPO / "notebooks/01-foundations/00-smoke.ipynb", tmp_path)
    assert main([str(tmp_path)]) == 0
    assert "PASS" in capsys.readouterr().out


def test_main_fails_when_no_notebooks_found(tmp_path, capsys):
    assert main([str(tmp_path)]) == 1
