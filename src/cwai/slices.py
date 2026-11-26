"""The eight canonical slices of the road-safety data.

Each student picks one slice. Eight slices mean eight right answers, so a
self-check cannot look an answer up. It recomputes the answer from the
definitions in this file.
"""

from __future__ import annotations

import difflib
from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from cwai import data

# Casualty type codes in the STATS19 data.
_PEDESTRIAN = 0
_CYCLIST = 1

# Light condition codes for darkness: lights lit, lights unlit, no lighting,
# lighting unknown. This is a fixed set, not "anything except daylight".
_DARK = (4, 5, 6, 7)


class UnknownSliceError(KeyError):
    """The slice id is not one of the eight slices."""

    def __str__(self) -> str:  # KeyError would otherwise show the repr, in quotes
        return str(self.args[0])


class NoDenominatorError(ValueError):
    """The slice has no traffic-count column to divide by."""


@dataclass(frozen=True)
class Slice:
    id: str
    label: str
    table: str  # "collisions" or "casualties"
    denominator: str | None
    select: Callable[[pd.DataFrame], pd.Series]


def _district(code: str) -> Callable[[pd.DataFrame], pd.Series]:
    return lambda df: df["local_authority_ons_district"] == code


SLICES: tuple[Slice, ...] = (
    Slice(
        "cyclists",
        "Cyclists",
        "casualties",
        "pedal_cycles",
        lambda df: df["casualty_type"] == _CYCLIST,
    ),
    Slice(
        "pedestrians",
        "Pedestrians",
        "casualties",
        None,
        lambda df: df["casualty_type"] == _PEDESTRIAN,
    ),
    Slice("leeds", "Leeds", "collisions", "all_motor_vehicles", _district("E08000035")),
    Slice(
        "bradford",
        "Bradford",
        "collisions",
        "all_motor_vehicles",
        _district("E08000032"),
    ),
    Slice(
        "kirklees",
        "Kirklees",
        "collisions",
        "all_motor_vehicles",
        _district("E08000034"),
    ),
    Slice(
        "wakefield",
        "Wakefield",
        "collisions",
        "all_motor_vehicles",
        _district("E08000036"),
    ),
    Slice(
        "calderdale",
        "Calderdale",
        "collisions",
        "all_motor_vehicles",
        _district("E08000033"),
    ),
    Slice(
        "after-dark",
        "After dark",
        "collisions",
        None,
        lambda df: df["light_conditions"].isin(_DARK),
    ),
)

_BY_ID = {s.id: s for s in SLICES}


def list_slices() -> list[str]:
    return [s.id for s in SLICES]


def get(slice_id: str) -> Slice:
    try:
        return _BY_ID[slice_id]
    except KeyError:
        pass
    ids = list_slices()
    near = difflib.get_close_matches(str(slice_id), ids, n=3)
    if near:
        hint = f"Did you mean {' or '.join(repr(n) for n in near)}?"
    else:
        hint = f"The slices are: {', '.join(ids)}."
    raise UnknownSliceError(
        f"There is no slice called {slice_id!r}. {hint} "
        "Check the spelling of the slice id and try again."
    ) from None


def load(slice_id: str) -> pd.DataFrame:
    s = get(slice_id)
    df = data.load_collisions() if s.table == "collisions" else data.load_casualties()
    return df[s.select(df)]


def ksi(df: pd.DataFrame, table: str) -> pd.Series:
    """Mask of killed or seriously injured rows (Fatal or Serious)."""
    if table == "collisions":
        return df["severity_label"].isin(["Fatal", "Serious"])
    if table == "casualties":
        return df["casualty_severity"].isin([1, 2])
    raise ValueError(f"Unknown table {table!r}. Use 'collisions' or 'casualties'.")


def denominator_column(slice_id: str) -> str:
    s = get(slice_id)
    if s.denominator is None:
        raise NoDenominatorError(
            f"The slice {s.id!r} has no denominator column. "
            "The traffic counts do not measure this group, so you cannot "
            "calculate a rate for it. Use a count or a percentage instead."
        )
    return s.denominator


@dataclass(frozen=True)
class SliceMetric:
    name: str
    kind: str
    tolerance: float
    compute: Callable[[Slice], object]


def _row_count(s: Slice) -> int:
    return len(load(s.id))


def _ksi_percent(s: Slice) -> float:
    df = load(s.id)
    return float(ksi(df, s.table).mean() * 100)


METRICS: dict[str, SliceMetric] = {
    "slice-row-count": SliceMetric("slice-row-count", "number", 0, _row_count),
    "slice-ksi-percent": SliceMetric(
        "slice-ksi-percent", "number", 0.001, _ksi_percent
    ),
}
