"""Cut the large national DfT files down to the small West Yorkshire subsets.

Input is the raw CSVs that ``scripts/fetch.py`` leaves in ``raw/``; output is
the Parquet files named in ``cwai.registry``. The subsets keep the messiness
students are meant to meet (blank severities, missing coordinates, coded
fields) and drop only rows that are out of scope or impossible.

Run ``python scripts/build_subsets.py RAW_DIR`` once raw files are downloaded.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pandas as pd

from cwai import registry

# The five West Yorkshire metropolitan districts (ONS codes), selected on code
# rather than name so spelling changes upstream cannot lose or add rows.
WEST_YORKSHIRE_ONS = frozenset(
    {
        "E08000032",  # Bradford
        "E08000033",  # Calderdale
        "E08000034",  # Kirklees
        "E08000035",  # Leeds
        "E08000036",  # Wakefield
    }
)

COLLISION_COLUMNS: tuple[str, ...] = (
    "accident_index",
    "accident_year",
    "longitude",
    "latitude",
    "accident_severity",
    "number_of_vehicles",
    "number_of_casualties",
    "date",
    "day_of_week",
    "time",
    "local_authority_ons_district",
    "road_type",
    "speed_limit",
    "light_conditions",
    "weather_conditions",
    "road_surface_conditions",
)
CASUALTY_COLUMNS: tuple[str, ...] = (
    "accident_index",
    "accident_year",
    "vehicle_reference",
    "casualty_reference",
    "casualty_class",
    "sex_of_casualty",
    "age_of_casualty",
    "casualty_severity",
    "casualty_type",
)
VEHICLE_COLUMNS: tuple[str, ...] = (
    "accident_index",
    "accident_year",
    "vehicle_reference",
    "vehicle_type",
    "vehicle_manoeuvre",
    "sex_of_driver",
    "age_of_driver",
    "age_of_vehicle",
)
COUNT_COLUMNS: tuple[str, ...] = (
    "count_point_id",
    "year",
    "region_name",
    "local_authority_name",
    "local_authority_code",
    "road_name",
    "road_type",
    "latitude",
    "longitude",
    "estimation_method",
    "pedal_cycles",
    "cars_and_taxis",
    "buses_and_coaches",
    "lgvs",
    "all_hgvs",
    "all_motor_vehicles",
)

# DfT is renaming "accident" to "collision" across its publications. Accept
# either on the way in; always emit the "accident" names on the way out.
_ALIASES = {
    "collision_index": "accident_index",
    "collision_year": "accident_year",
    "collision_severity": "accident_severity",
}

_SEVERITY_LABELS = {1: "Fatal", 2: "Serious", 3: "Slight"}
_SEVERITY_TYPE = pd.CategoricalDtype(list(_SEVERITY_LABELS.values()), ordered=True)

_TEXT = {
    "accident_index",
    "time",
    "local_authority_ons_district",
    "local_authority_code",
    "local_authority_name",
    "region_name",
    "road_name",
    "estimation_method",
}
_FLOAT = {"longitude", "latitude"}
_DATE = {"date"}


def _normalise(name: str) -> str:
    name = name.strip().lower()
    return _ALIASES.get(name, name)


def _read(
    raw_csv: Path, columns: tuple[str, ...], text: frozenset[str] = frozenset()
) -> pd.DataFrame:
    """Read ``columns`` from ``raw_csv`` with typed, boundary-normalised names."""
    header = pd.read_csv(raw_csv, nrows=0).columns
    renamed = {col: _normalise(col) for col in header}
    seen = set(renamed.values())
    missing = [c for c in columns if c not in seen]
    if missing:
        names = ", ".join(missing)
        raise ValueError(f"{raw_csv} is missing required column(s): {names}")
    wanted = {col for col, new in renamed.items() if new in columns}
    df = pd.read_csv(raw_csv, usecols=lambda c: c in wanted, dtype=str)
    df = df.rename(columns=renamed)[list(columns)]
    for col in df.columns:
        if col in _DATE:
            df[col] = pd.to_datetime(df[col], format="%d/%m/%Y")
        elif col in _FLOAT:
            df[col] = pd.to_numeric(df[col])
        elif col not in _TEXT and col not in text:
            df[col] = pd.to_numeric(df[col]).astype("Int64")
    return df


def _write(df: pd.DataFrame, out: Path) -> pd.DataFrame:
    df = df.reset_index(drop=True)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    return df


def _in_years(series: pd.Series) -> pd.Series:
    return series.isin(registry.YEARS)


def build_collisions(raw_csv: Path, out: Path) -> pd.DataFrame:
    """West Yorkshire collisions in ``registry.YEARS``, with a severity label."""
    df = _read(raw_csv, COLLISION_COLUMNS)
    df = df[
        _in_years(df.accident_year)
        & df.local_authority_ons_district.isin(WEST_YORKSHIRE_ONS)
    ]
    # (0, 0) is a placeholder for "unknown", not a place in the Gulf of Guinea.
    # Genuinely blank coordinates are kept: they are a data-quality lesson.
    df = df[~((df.longitude == 0) & (df.latitude == 0))]
    df["severity_label"] = pd.Categorical(
        df.accident_severity.map(_SEVERITY_LABELS), dtype=_SEVERITY_TYPE
    )
    return _write(df, out)


def _filter_children(
    df: pd.DataFrame, accident_index: pd.Series | None
) -> pd.DataFrame:
    df = df[_in_years(df.accident_year)]
    if accident_index is not None:
        df = df[df.accident_index.isin(set(accident_index))]
    return df


def build_casualties(
    raw_csv: Path, out: Path, accident_index: pd.Series | None = None
) -> pd.DataFrame:
    """Casualties in ``registry.YEARS``, limited to ``accident_index`` if given.

    The casualty file has no area column, so pass the ``accident_index`` of the
    built collisions to restrict it to West Yorkshire.
    """
    df = _read(raw_csv, CASUALTY_COLUMNS)
    return _write(_filter_children(df, accident_index), out)


def build_vehicles(
    raw_csv: Path, out: Path, accident_index: pd.Series | None = None
) -> pd.DataFrame:
    """Vehicles in ``registry.YEARS``, limited to ``accident_index`` if given."""
    df = _read(raw_csv, VEHICLE_COLUMNS)
    return _write(_filter_children(df, accident_index), out)


def build_counts(raw_csv: Path, out: Path) -> pd.DataFrame:
    """AADF traffic counts for West Yorkshire in ``registry.YEARS``."""
    # road_type is a name ("Major"/"Minor") here but a numeric code in STATS19.
    df = _read(raw_csv, COUNT_COLUMNS, text=frozenset({"road_type"}))
    df = df[_in_years(df.year) & df.local_authority_code.isin(WEST_YORKSHIRE_ONS)]
    return _write(df, out)


def main(argv: list[str] | None = None) -> int:
    """Build all four subsets from a ``raw/`` directory of fetched files."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: build_subsets.py RAW_DIR", file=sys.stderr)
        return 2
    raw = Path(args[0])
    root = registry.data_root()

    def target(key: str) -> Path:
        return root / registry.get(key).relpath

    collisions = _build_many(raw, "collision", build_collisions, target("collisions"))
    index = collisions.accident_index
    _build_many(raw, "casualty", build_casualties, target("casualties"), index)
    _build_many(raw, "vehicle", build_vehicles, target("vehicles"), index)
    build_counts(next(raw.glob("dft_traffic_counts_aadf*")), target("traffic-counts"))
    return 0


def _build_many(raw: Path, stem: str, builder, out: Path, *extra) -> pd.DataFrame:
    """Run ``builder`` over every per-year file for ``stem`` and combine."""
    files = sorted(raw.glob(f"dft-road-casualty-statistics-{stem}-*.csv"))
    if not files:
        raise FileNotFoundError(f"no {stem} CSVs in {raw}; run scripts/fetch.py first")
    with tempfile.TemporaryDirectory() as scratch:
        frames = [builder(f, Path(scratch) / f.name, *extra) for f in files]
    return _write(pd.concat(frames, ignore_index=True), out)


if __name__ == "__main__":
    raise SystemExit(main())
