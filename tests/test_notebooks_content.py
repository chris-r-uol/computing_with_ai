"""What the reference lesson must contain, and must keep containing.

``tests/test_student_notebooks.py`` tests the stripping machinery on fixtures.
This module tests the one real lesson built on that machinery: it runs, its
stripped copy runs, every exercise has hints, every check name resolves, every
mechanism is used, no student's slice is worked through, and the prose passes
the gate.
"""

from __future__ import annotations

import re
from pathlib import Path

import check_prose
import nbformat
import run_notebooks
import yaml
from build_student_notebooks import check_notebook_hints, exercise_ids

from cwai import checks, slices

REPO = Path(__file__).resolve().parent.parent
LESSON = REPO / "notebooks" / "01-foundations" / "01-first-look.ipynb"
STUDENT_LESSON = REPO / "student" / "01-foundations" / "01-first-look.ipynb"
HINTS_FILE = REPO / "hints" / "01-foundations.yml"

# check("name", ...) and check_slice("name", ...): the name is the first
# argument, so the opening of the call is enough to read it.
_CHECK_CALL = re.compile(r"\bcheck(?:_slice)?\(\s*[\"']([^\"']+)[\"']")


def all_source(path: Path) -> str:
    """Every cell's source in one string, in notebook order."""
    nb = nbformat.read(path, as_version=4)
    return "\n".join(cell.source for cell in nb.cells)


def check_names_called(path: Path) -> list[str]:
    """The check names the notebook passes to ``check`` or ``check_slice``."""
    return _CHECK_CALL.findall(all_source(path))


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


def test_the_lesson_exercises_each_mechanism_once():
    source = all_source(LESSON)
    for call in ("hint(", "reveal(", "check(", "check_slice("):
        assert call in source, f"the lesson never calls {call}"


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
