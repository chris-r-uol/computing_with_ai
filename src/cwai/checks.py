"""Self-checks: let a student test an answer against a known truth.

Answers live in ``checks/expected.json``. Its shape is pinned by
``checks/expected.schema.json`` and the comparison rules are written down in
``checks/README.md``. This module is the only implementation of those rules.
Every message a student can see says what was expected, what was found, and
what to do next.
"""

from __future__ import annotations

import difflib
import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from cwai import registry, slices

TOLERANCE = 1e-6

UNATTEMPTED = Ellipsis

_EXPECTED_PATH = registry.repo_root() / "checks" / "expected.json"


class UnknownCheckError(KeyError):
    """The check name is not in expected.json."""

    def __str__(self) -> str:  # KeyError would otherwise show the repr, in quotes
        return str(self.args[0])


class CheckFailed(AssertionError):
    """A structural expectation about a DataFrame was not met."""


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    message: str
    attempted: bool = True

    def __bool__(self) -> bool:
        return self.passed

    def __repr__(self) -> str:
        # Three marks with three different shapes, so no state depends on colour.
        # The third state is never a cross: an untouched exercise is not a wrong one.
        if not self.attempted:
            return f"○ {self.name}: {self.message}"
        mark = "✓" if self.passed else "✗"
        return f"{mark} {self.name}: {self.message}"


_UNATTEMPTED_MESSAGE = (
    "not attempted yet. Replace the ... with your answer, then run the cell again."
)


def _unattempted(name: str) -> CheckResult:
    return CheckResult(name, False, _UNATTEMPTED_MESSAGE, attempted=False)


def load_expected(path: Path | None = None) -> dict:
    return json.loads(Path(path or _EXPECTED_PATH).read_text(encoding="utf-8"))


def _plain(value: object) -> object:
    """Numpy scalars/arrays and tuples to plain Python, for comparison."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    return list(value) if isinstance(value, tuple) else value


def _short(value: object, limit: int = 60) -> str:
    """repr(value), cut short so a whole table never lands in an error message."""
    text = repr(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _article(value: object) -> str:
    """'a DataFrame', 'a str': name what was passed instead of printing it."""
    name = type(value).__name__
    return f"{'an' if name[0] in 'AEIOU' else 'a'} {name}"


_PLAIN_TYPES = (str, bytes, bool, int, float, type(None), list, tuple, dict)


def _describe(value: object) -> str:
    """Show small plain values as written ('42'), name anything else."""
    if isinstance(value, _PLAIN_TYPES) and len(repr(value)) <= 60:
        return repr(value)
    return _article(value)


def _compare(
    kind: str, expected: object, tolerance: float, value: object
) -> str | None:
    """Return None if value matches, else a teaching sentence."""
    if kind == "number":
        number = _plain(value)
        if isinstance(number, bool) or not isinstance(number, int | float):
            return (
                f"Expected a number ({expected}) but found {_describe(value)}, "
                "which is not a number. Check that you are passing the result itself, "
                "not text or a table."
            )
        if math.isclose(number, expected, rel_tol=0, abs_tol=tolerance):
            return None
        return (
            f"Expected {expected} but found {number}. "
            "Re-read the question, check your calculation, and run the cell again."
        )
    if kind == "shape":
        found = _plain(getattr(value, "shape", value))
        if found == list(expected):
            return None
        return (
            f"Expected a shape of {tuple(expected)} but found "
            f"{_short(tuple(found) if isinstance(found, list) else found)}. "
            "Check how many rows and columns your result has."
        )
    found = _plain(value)
    if found == expected:
        return None
    if kind == "list":
        noun, advice = "list", "Compare them item by item"
    else:
        noun, advice = "text", "Check the spelling, capital letters and spaces"
    return (
        f"Expected the {noun} {expected!r} but found {_short(found)}. "
        f"{advice}, fix your answer, and run the cell again."
    )


def _unknown_name_message(name: str, known: Iterable[str]) -> str:
    near = difflib.get_close_matches(name, list(known), n=3)
    hint = (
        f"Did you mean {' or '.join(repr(n) for n in near)}?"
        if near
        else "Check the spelling against the name given in the notebook."
    )
    return (
        f"There is no check called {name!r}. {hint} "
        "The name must match the one in the notebook exactly."
    )


def check(name: str, value: object) -> CheckResult:
    """Compare ``value`` with the stored answer called ``name``."""
    expected = load_expected()
    if name not in expected:
        raise UnknownCheckError(_unknown_name_message(name, expected))
    if value is UNATTEMPTED:
        return _unattempted(name)
    entry = expected[name]
    problem = _compare(
        entry["type"], entry["value"], entry.get("tolerance", TOLERANCE), value
    )
    if problem is None:
        return CheckResult(name, True, "passed")
    return CheckResult(name, False, problem)


def expect_columns(df, columns: Iterable[str]) -> None:
    """Raise CheckFailed unless every named column is present."""
    if df is UNATTEMPTED:
        return
    wanted = list(columns)
    missing = [c for c in wanted if c not in df.columns]
    if missing:
        raise CheckFailed(
            f"Expected columns {wanted} but the table is missing {missing}; "
            f"it has {list(df.columns)}. Check the spelling of the column names "
            "or the step that creates them."
        )


def expect_shape(df, rows: int | None = None, cols: int | None = None) -> None:
    """Raise CheckFailed unless the table has the stated rows and/or columns."""
    if rows is None and cols is None:
        # Otherwise this passes silently and a student gets a tick for nothing.
        raise ValueError(
            "expect_shape needs something to check: pass rows=, cols=, or both, "
            "as in expect_shape(df, rows=12) or expect_shape(df, rows=12, cols=3)."
        )
    if df is UNATTEMPTED:
        return
    found_rows, found_cols = df.shape
    wanted, found = [], []
    if rows is not None and found_rows != rows:
        wanted.append(f"{rows} row{'' if rows == 1 else 's'}")
        found.append(f"{found_rows} row{'' if found_rows == 1 else 's'}")
    if cols is not None and found_cols != cols:
        wanted.append(f"{cols} column{'' if cols == 1 else 's'}")
        found.append(f"{found_cols} column{'' if found_cols == 1 else 's'}")
    if wanted:
        raise CheckFailed(
            f"Expected {' and '.join(wanted)} but found {' and '.join(found)}. "
            "Check any filtering, merging or dropping steps before this point."
        )


def check_slice(name: str, value: object, slice_id: str) -> CheckResult:
    """Compare ``value`` with the answer for one student's slice of the data.

    A handoff has two stubs, not one: the answer, and the slice id it is for.
    Either left untouched is an unattempted exercise, so an unpicked slice gets
    the same neutral result as an unanswered question. A student who has not
    chosen a slice yet has not got an exercise wrong.

    An unknown ``slice_id`` still raises ``slices.UnknownSliceError``, which
    explains itself: only the stub sentinel is read as unattempted, so a typo
    is never excused. An unknown ``name`` raises ``UnknownCheckError``, and it
    is checked first, because that is a mistake in the course material rather
    than a blank answer.
    """
    if name not in slices.METRICS:
        raise UnknownCheckError(_unknown_name_message(name, slices.METRICS))
    if slice_id is UNATTEMPTED or value is UNATTEMPTED:
        return _unattempted(name)
    the_slice = slices.get(slice_id)
    metric = slices.METRICS[name]
    problem = _compare(metric.kind, metric.compute(the_slice), metric.tolerance, value)
    if problem is None:
        return CheckResult(name, True, "passed")
    return CheckResult(name, False, problem)
