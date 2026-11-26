"""What the reference lesson must contain, and must keep containing.

``tests/test_student_notebooks.py`` tests the stripping machinery on fixtures.
This module tests the one real lesson built on that machinery: it runs, its
stripped copy runs, every exercise has hints, every check name resolves, every
answer it checks is still true, every mechanism is used, no student's slice is
worked through, and the prose passes the gate.
"""

from __future__ import annotations

import re
from pathlib import Path

import check_prose
import nbformat
import run_notebooks
import yaml
from build_student_notebooks import check_notebook_hints, exercise_ids
from nbclient import NotebookClient

from cwai import checks, slices

REPO = Path(__file__).resolve().parent.parent
LESSON = REPO / "notebooks" / "01-foundations" / "01-first-look.ipynb"
STUDENT_LESSON = REPO / "student" / "01-foundations" / "01-first-look.ipynb"
HINTS_FILE = REPO / "hints" / "01-foundations.yml"

# check("name", ...) and check_slice("name", ...): the name is the first
# argument, so the opening of the call is enough to read it.
_CHECK_CALL = re.compile(r"\bcheck(?:_slice)?\(\s*[\"']([^\"']+)[\"']")
# One printed CheckResult: its mark, then the check name it is about.
_RESULT_LINE = re.compile(r"^([✓✗○])\s+(\S+?):")


def all_source(path: Path) -> str:
    """Every cell's source in one string, in notebook order."""
    nb = nbformat.read(path, as_version=4)
    return "\n".join(cell.source for cell in nb.cells)


def check_names_called(path: Path) -> list[str]:
    """The check names the notebook passes to ``check`` or ``check_slice``.

    Code cells only. ``all_source`` joins every cell, so a markdown line that
    mentions a ``check(...)`` call -- a lesson explaining the mechanism, say --
    would otherwise be counted as a call that produced no result.
    """
    nb = nbformat.read(path, as_version=4)
    code = "\n".join(c.source for c in nb.cells if c.cell_type == "code")
    return _CHECK_CALL.findall(code)


def _executed(path: Path) -> nbformat.NotebookNode:
    """The notebook, run in a fresh kernel, with its outputs kept.

    ``run_notebooks.run`` reports whether a notebook ran and throws the outputs
    away, which is all it needs. The test below reads the outputs, so it runs
    the notebook on the same settings and keeps them.
    """
    nb = nbformat.read(path, as_version=4)
    NotebookClient(
        nb,
        timeout=run_notebooks.TIMEOUT_SECONDS,
        kernel_name="python3",
        allow_errors=False,
        resources={"metadata": {"path": str(REPO)}},
    ).execute()
    return nb


def check_result_lines(nb: nbformat.NotebookNode) -> list[str]:
    """Every line of output that a ``CheckResult`` printed, in notebook order.

    ``CheckResult.__repr__`` opens with one of three marks, so the mark alone
    says which of the three states a check landed in.
    """
    lines = []
    for cell in nb.cells:
        for output in cell.get("outputs", []):
            text = output.get("text") or (output.get("data") or {}).get(
                "text/plain", ""
            )
            lines += [
                line.strip()
                for line in str(text).splitlines()
                if line.strip()[:1] in {"✓", "✗", "○"}
            ]
    return lines


def test_the_reference_lesson_runs_standalone_within_the_time_limit():
    result = run_notebooks.run(LESSON)
    assert result.passed, result.error
    assert result.seconds < run_notebooks.TIMEOUT_SECONDS


def test_the_stripped_lesson_also_runs_standalone():
    """What the site executes is the stripped copy, so that is what must run."""
    assert run_notebooks.run(STUDENT_LESSON).passed


def test_every_exercise_in_the_lesson_has_its_hints():
    check_notebook_hints(LESSON)  # raises MissingHintError if not


def test_every_check_name_the_lesson_uses_resolves():
    called = check_names_called(LESSON)
    assert called, "the lesson calls no check at all"
    for name in called:
        assert name in checks.load_expected() or name in slices.METRICS


def test_every_stored_answer_the_full_lesson_checks_is_still_true():
    """Not that the lesson runs: that the answers it checks against are right.

    ``checks/expected.json`` holds answers measured from the data by hand, and a
    rebuilt data subset moves them without breaking anything the other tests
    watch. The lesson would still run, its page would still render, and every
    student's exercise would quietly be marked wrong.

    Every exercise checked against a stored answer has its solution in the full
    notebook, so each of those must read as passed. A handoff is the one
    exception, and it is not an exemption: it ships ``my_slice = ...``, because
    no student's slice may be the lesson's default, so it reads as unattempted
    here -- and it has no stored answer to go stale, since ``check_slice``
    recomputes from ``slices.METRICS``. Nothing may read as wrong either way.
    """
    lines = check_result_lines(_executed(LESSON))
    assert len(lines) == len(check_names_called(LESSON)), (
        f"expected one result per check call, found {lines}"
    )
    results = {}
    for line in lines:
        match = _RESULT_LINE.match(line)
        assert match, f"could not read a check result out of {line!r}"
        results[match.group(2)] = (match.group(1), line)

    wrong = [line for mark, line in results.values() if mark == "✗"]
    assert not wrong, "a check in the full lesson is wrong:\n" + "\n".join(wrong)

    stored = checks.load_expected()
    missed = [
        line for name, (mark, line) in results.items() if mark != "✓" and name in stored
    ]
    assert not missed, "a check against a stored answer did not pass:\n" + "\n".join(
        missed
    )


def test_the_lesson_exercises_each_mechanism_once():
    source = all_source(LESSON)
    for call in ("hint(", "reveal(", "check(", "check_slice("):
        assert call in source, f"the lesson never calls {call}"


def test_the_lesson_shows_which_table_each_slice_cuts_before_it_asks():
    """Exercise 4 asks the student to say whether they counted people.

    The lesson used to print ``slices.list_slices()``, which is eight bare
    ids, and nothing on the page said which slices hold people. A student on
    ``cyclists`` could not answer the question they were being asked. The
    lesson and the workbook template now show the same
    ``slices.shortlist()``, whose ``table`` column answers it.
    """
    source = all_source(LESSON)
    assert "slices.shortlist()" in source, "the lesson prints no slice table"
    assert "`table` column" in source, "nothing in the prose points at it"


def test_the_lesson_teaches_on_the_demo_slice_not_a_students_slice():
    """No student's chosen slice may be worked through for them."""
    source = all_source(LESSON)
    for slice_id in slices.list_slices():
        assert f'load("{slice_id}")' not in source


def test_the_lesson_shows_an_answer_tier_and_a_three_tier_exercise():
    """One written exercise and one coding exercise, so both shapes are proved."""
    hints = yaml.safe_load(HINTS_FILE.read_text(encoding="utf-8"))
    ids = exercise_ids(nbformat.read(LESSON, as_version=4))
    used = [hints[i] for i in ids]
    assert any("answer" in tiers for tiers in used)
    assert any({"nudge", "method", "code"} <= set(tiers) for tiers in used)


def test_the_lessons_prose_and_hints_pass_the_prose_gate():
    assert check_prose.check_notebook(LESSON) == []
    assert check_prose.check_hints(HINTS_FILE) == []
