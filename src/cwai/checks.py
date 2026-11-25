"""Self-checks: let a student test an answer against a known truth.

Answers live in ``checks/expected.json``, which the website's JavaScript reads
too; its shape is pinned by ``checks/expected.schema.json``. Every message a
student can see says what was expected, what was found, and what to do next.
"""

from __future__ import annotations

import difflib
import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

TOLERANCE = 1e-6

_EXPECTED_PATH = Path(__file__).resolve().parents[2] / "checks" / "expected.json"


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

    def __bool__(self) -> bool:
        return self.passed

    def __repr__(self) -> str:
        mark = "✓" if self.passed else "✗"
        return f"{mark} {self.name}: {self.message}"


def load_expected(path: Path | None = None) -> dict:
    return json.loads(Path(path or _EXPECTED_PATH).read_text(encoding="utf-8"))


def _plain(value: object) -> object:
    """Numpy scalars/arrays and tuples to plain Python, for comparison."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    return list(value) if isinstance(value, tuple) else value


def _compare(
    kind: str, expected: object, tolerance: float, value: object
) -> str | None:
    """Return None if value matches, else a teaching sentence."""
    if kind == "number":
        number = _plain(value)
        if isinstance(number, bool) or not isinstance(number, int | float):
            return (
                f"Expected a number ({expected}) but found {value!r}, which is not a "
                "number. Check that you are passing the result itself, "
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
            f"{tuple(found) if isinstance(found, list) else found!r}. "
            "Check how many rows and columns your result has."
        )
    found = _plain(value)
    if found == expected:
        return None
    noun = "list" if kind == "list" else "text"
    return (
        f"Expected the {noun} {expected!r} but found {found!r}. "
        "Compare them item by item, fix your answer, and run the cell again."
    )


def check(name: str, value: object) -> CheckResult:
    """Compare ``value`` with the stored answer called ``name``."""
    expected = load_expected()
    if name not in expected:
        near = difflib.get_close_matches(name, expected, n=3)
        hint = (
            f"Did you mean {' or '.join(repr(n) for n in near)}?"
            if near
            else "Check the spelling against the name given in the notebook."
        )
        raise UnknownCheckError(
            f"There is no check called {name!r}. {hint} "
            "The name must match the one in the notebook exactly."
        )
    entry = expected[name]
    problem = _compare(
        entry["type"], entry["value"], entry.get("tolerance", TOLERANCE), value
    )
    if problem is None:
        return CheckResult(name, True, "passed")
    return CheckResult(name, False, problem)


def expect_columns(df, columns: Iterable[str]) -> None:
    """Raise CheckFailed unless every named column is present."""
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
