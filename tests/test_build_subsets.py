from pathlib import Path

import pandas as pd
import pytest
from build_subsets import (
    COLLISION_COLUMNS,
    WEST_YORKSHIRE_ONS,
    build_casualties,
    build_collisions,
    build_counts,
    build_vehicles,
)

from cwai.registry import YEARS

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURES / "stats19_collisions_sample.csv"
CASUALTIES = FIXTURES / "stats19_casualties_sample.csv"
VEHICLES = FIXTURES / "stats19_vehicles_sample.csv"
COUNTS = FIXTURES / "dft_counts_sample.csv"


def test_collisions_keeps_only_target_area_and_years(tmp_path):
    df = build_collisions(FIXTURE, tmp_path / "c.parquet")
    assert set(df.accident_year) <= set(YEARS)
    assert df.local_authority_ons_district.str.startswith("E08").all()
    # Manchester and Sheffield are E08 too: selection is by code, not by prefix.
    assert set(df.local_authority_ons_district) <= WEST_YORKSHIRE_ONS
    assert len(df) == 26


def test_collisions_columns_exactly_match_declared_set(tmp_path):
    df = build_collisions(FIXTURE, tmp_path / "c.parquet")
    assert tuple(df.columns) == COLLISION_COLUMNS + ("severity_label",)


def test_severity_label_is_ordered_categorical(tmp_path):
    df = build_collisions(FIXTURE, tmp_path / "c.parquet")
    assert list(df.severity_label.cat.categories) == ["Fatal", "Serious", "Slight"]
    assert df.severity_label.cat.ordered


def test_severity_code_maps_to_label_and_each_code_is_present(tmp_path):
    df = build_collisions(FIXTURE, tmp_path / "c.parquet")
    known = df.dropna(subset=["accident_severity"])
    pairs = set(zip(known.accident_severity, known.severity_label, strict=True))
    assert pairs == {(1, "Fatal"), (2, "Serious"), (3, "Slight")}


def test_missing_severity_is_kept_with_missing_label(tmp_path):
    df = build_collisions(FIXTURE, tmp_path / "c.parquet")
    missing = df[df.accident_severity.isna()]
    assert len(missing) == 1
    assert missing.severity_label.isna().all()


def test_parquet_roundtrips_dtypes(tmp_path):
    out = tmp_path / "c.parquet"
    df = build_collisions(FIXTURE, out)
    assert pd.read_parquet(out).dtypes.to_dict() == df.dtypes.to_dict()


def test_implausible_coordinates_are_dropped_not_zeroed(tmp_path):
    # fixture contains a row at lon=0, lat=0
    df = build_collisions(FIXTURE, tmp_path / "c.parquet")
    assert not ((df.longitude == 0) & (df.latitude == 0)).any()


def test_missing_coordinates_are_kept_as_missing(tmp_path):
    df = build_collisions(FIXTURE, tmp_path / "c.parquet")
    assert df.longitude.isna().sum() == 1


def test_date_is_parsed_day_first(tmp_path):
    df = build_collisions(FIXTURE, tmp_path / "c.parquet")
    first = df.iloc[0]
    assert first.date == pd.Timestamp("2021-01-05")


def test_old_accident_naming_is_accepted_and_gives_identical_output(tmp_path):
    old = pd.read_csv(FIXTURE, dtype=str, keep_default_na=False).rename(
        columns={
            "collision_index": "accident_index",
            "collision_year": "accident_year",
            "collision_severity": "accident_severity",
        }
    )
    old_csv = tmp_path / "old.csv"
    old.to_csv(old_csv, index=False)
    a = build_collisions(old_csv, tmp_path / "a.parquet")
    b = build_collisions(FIXTURE, tmp_path / "b.parquet")
    pd.testing.assert_frame_equal(a, b)


def test_missing_required_column_names_the_column(tmp_path):
    bad = pd.read_csv(FIXTURE).drop(columns=["speed_limit"])
    bad_csv = tmp_path / "bad.csv"
    bad.to_csv(bad_csv, index=False)
    with pytest.raises(ValueError, match="speed_limit"):
        build_collisions(bad_csv, tmp_path / "x.parquet")


def test_casualties_follow_the_collision_subset(tmp_path):
    collisions = build_collisions(FIXTURE, tmp_path / "c.parquet")
    df = build_casualties(
        CASUALTIES, tmp_path / "k.parquet", accident_index=collisions.accident_index
    )
    assert len(df) == 12
    assert df.accident_index.isin(collisions.accident_index).all()
    assert "accident_year" in df.columns
    assert pd.read_parquet(tmp_path / "k.parquet").shape == df.shape


def test_casualties_without_collision_subset_filter_by_year_only(tmp_path):
    df = build_casualties(CASUALTIES, tmp_path / "k.parquet")
    assert set(df.accident_year) <= set(YEARS)
    assert len(df) == 13


def test_vehicles_follow_the_collision_subset(tmp_path):
    collisions = build_collisions(FIXTURE, tmp_path / "c.parquet")
    df = build_vehicles(
        VEHICLES, tmp_path / "v.parquet", accident_index=collisions.accident_index
    )
    assert len(df) == 12
    assert df.accident_index.isin(collisions.accident_index).all()


def test_counts_keep_only_target_area_and_years(tmp_path):
    df = build_counts(COUNTS, tmp_path / "a.parquet")
    assert set(df.year) <= set(YEARS)
    assert set(df.local_authority_code) <= WEST_YORKSHIRE_ONS
    assert len(df) == 22
    stored = pd.read_parquet(tmp_path / "a.parquet")
    assert stored.dtypes.to_dict() == df.dtypes.to_dict()
