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


def test_counts_keep_target_area_and_every_year(tmp_path):
    df = build_counts(COUNTS, tmp_path / "a.parquet")
    assert set(df.local_authority_code) <= WEST_YORKSHIRE_ONS
    # Earlier years (the pre-COVID baseline) must survive, not be filtered out.
    assert {2000, 2015, 2019} <= set(df.year)
    assert set(YEARS) <= set(df.year)
    assert len(df) == 25
    stored = pd.read_parquet(tmp_path / "a.parquet")
    assert stored.dtypes.to_dict() == df.dtypes.to_dict()


# --- guards against silently empty or shrunken subsets ---------------------


def _with_column(src, tmp_path, column, transform, name="mod.csv"):
    df = pd.read_csv(src, dtype=str, keep_default_na=False)
    df[column] = transform(df[column])
    out = tmp_path / name
    df.to_csv(out, index=False)
    return out


def test_collisions_raise_when_district_codes_match_nothing(tmp_path):
    bad = _with_column(
        FIXTURE, tmp_path, "local_authority_ons_district", lambda s: s.str.lower()
    )
    out = tmp_path / "c.parquet"
    with pytest.raises(ValueError) as err:
        build_collisions(bad, out)
    message = str(err.value)
    assert "local_authority_ons_district" in message
    assert "matched none" in message
    assert "e08000035" in message  # a value actually found
    assert not out.exists()


def test_collisions_raise_when_district_is_numeric_ids(tmp_path):
    bad = _with_column(
        FIXTURE, tmp_path, "local_authority_ons_district", lambda s: "108"
    )
    with pytest.raises(ValueError, match="'108'"):
        build_collisions(bad, tmp_path / "c.parquet")


def test_counts_raise_when_area_codes_match_nothing(tmp_path):
    bad = _with_column(
        COUNTS, tmp_path, "local_authority_code", lambda s: s.str.lower()
    )
    with pytest.raises(ValueError, match="local_authority_code.*matched none"):
        build_counts(bad, tmp_path / "a.parquet")


def test_counts_raise_when_a_year_is_missing(tmp_path):
    df = pd.read_csv(COUNTS)
    partial = tmp_path / "partial.csv"
    df[df.year != YEARS[-1]].to_csv(partial, index=False)
    with pytest.raises(ValueError, match=str(YEARS[-1])):
        build_counts(partial, tmp_path / "a.parquet")


def test_children_raise_when_nothing_matches_collision_subset(tmp_path):
    with pytest.raises(ValueError, match="collision subset"):
        build_casualties(
            CASUALTIES, tmp_path / "k.parquet", accident_index=pd.Series(["nope"])
        )


# --- main(): the whole pipeline on fixtures ---------------------------------


def _raw_dir(tmp_path):
    import shutil

    raw = tmp_path / "raw"
    raw.mkdir()
    names = {
        CASUALTIES: "dft-road-casualty-statistics-casualty-2021.csv",
        VEHICLES: "dft-road-casualty-statistics-vehicle-2021.csv",
        FIXTURE: "dft-road-casualty-statistics-collision-2021.csv",
        COUNTS: "dft_traffic_counts_aadf.csv",
    }
    for src, name in names.items():
        shutil.copy(src, raw / name)
    return raw


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    import build_subsets

    monkeypatch.setattr(build_subsets.registry, "data_root", lambda: tmp_path / "out")
    return build_subsets, _raw_dir(tmp_path), tmp_path / "out"


def test_main_builds_four_non_empty_subsets_following_the_collision_index(pipeline):
    build_subsets, raw, out = pipeline
    assert build_subsets.main([str(raw)]) == 0
    frames = {
        name: pd.read_parquet(out / rel)
        for name, rel in {
            "collisions": "stats19/collisions.parquet",
            "casualties": "stats19/casualties.parquet",
            "vehicles": "stats19/vehicles.parquet",
            "counts": "dft-counts/aadf.parquet",
        }.items()
    }
    assert all(len(df) > 0 for df in frames.values())
    index = set(frames["collisions"].accident_index)
    assert set(frames["casualties"].accident_index) <= index
    assert set(frames["vehicles"].accident_index) <= index


def test_main_raises_helpfully_when_aadf_file_is_missing(pipeline):
    build_subsets, raw, _ = pipeline
    (raw / "dft_traffic_counts_aadf.csv").unlink()
    with pytest.raises(FileNotFoundError, match="AADF"):
        build_subsets.main([str(raw)])


def test_main_raises_when_collision_files_are_missing(pipeline):
    build_subsets, raw, _ = pipeline
    (raw / "dft-road-casualty-statistics-collision-2021.csv").unlink()
    with pytest.raises(FileNotFoundError, match="collision"):
        build_subsets.main([str(raw)])


def test_main_raises_when_downloaded_years_do_not_cover_years(pipeline):
    build_subsets, raw, _ = pipeline
    path = raw / "dft-road-casualty-statistics-collision-2021.csv"
    df = pd.read_csv(path)
    df[df.collision_year != YEARS[-1]].to_csv(path, index=False)
    with pytest.raises(ValueError, match=str(YEARS[-1])):
        build_subsets.main([str(raw)])
