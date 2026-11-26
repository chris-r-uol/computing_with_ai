"""Assertions about the data that is actually committed under ``data/``.

Every other test in the suite runs against hand-written CSV fixtures, so a
truncated, mis-columned or wrong-year ``collisions.parquet`` would keep the
whole suite green while every notebook built on it was wrong. These tests load
the committed files themselves, through the same loaders a student uses.

They are the only tests that fail when the data is rebuilt badly, so keep them
about the data's shape and coverage rather than its exact row counts, which
change at every upstream refresh.

The road and casualty facts at the foot of this file are the deliberate
exception, and they are pinned on purpose. Stage 2's whole thesis and two
numbers written into the stage 1 lesson's prose rest on them, so a rebuild that
moves one has to fail here rather than publish a page whose text asserts a
number its own output contradicts. Do not loosen those assertions into shape
checks; if a refresh moves one, change the material it belongs to as well.
"""

from __future__ import annotations

import pandas as pd
import pytest
from build_subsets import (
    CASUALTY_COLUMNS,
    COLLISION_COLUMNS,
    COUNT_COLUMNS,
    VEHICLE_COLUMNS,
)

from cwai import data, registry

YEARS = list(registry.YEARS)
# build_collisions adds this to the columns it keeps: the human-readable
# severity that the coded column does not give.
DERIVED_COLLISION_COLUMNS = (*COLLISION_COLUMNS, "severity_label")


@pytest.mark.parametrize("key", sorted(registry.REGISTRY))
def test_every_registered_dataset_is_present(key):
    path = registry.data_root() / registry.get(key).relpath
    assert path.is_file(), f"{path} is missing; see scripts/check_licences.py"
    assert path.stat().st_size > 0


@pytest.mark.parametrize(
    ("loader", "columns"),
    [
        ("load_collisions", DERIVED_COLLISION_COLUMNS),
        ("load_casualties", CASUALTY_COLUMNS),
        ("load_vehicles", VEHICLE_COLUMNS),
        ("load_traffic_counts", COUNT_COLUMNS),
    ],
)
def test_committed_table_loads_with_the_columns_it_was_built_with(loader, columns):
    df = getattr(data, loader)()
    assert not df.empty
    assert set(columns) <= set(df.columns), set(columns) - set(df.columns)


def test_collisions_carries_the_derived_severity_label():
    df = data.load_collisions()
    assert tuple(df.columns) == DERIVED_COLLISION_COLUMNS
    assert df["severity_label"].notna().any()


@pytest.mark.parametrize("key", ["collisions", "casualties", "vehicles"])
def test_stats19_covers_exactly_the_module_years(key):
    # Exactly: a missing year is a partial download, and an extra one means the
    # subsets and registry.YEARS have come apart.
    assert data.available_years(key) == YEARS


def test_traffic_counts_include_the_module_years_and_reach_further_back():
    years = data.available_years("traffic-counts")
    assert set(YEARS) <= set(years)
    # The counts are deliberately not cut to YEARS: the earlier years carry the
    # pre-COVID baseline and the 2020 collapse the collision tables cannot show.
    assert years[0] < YEARS[0], years[:3]
    assert 2020 in years


def test_the_two_datasets_overlap_only_where_the_data_page_says():
    collisions = set(data.available_years("collisions"))
    counts = set(data.available_years("traffic-counts"))
    assert collisions & counts == set(YEARS)


@pytest.mark.parametrize("place", ["leeds", "chengdu"])
@pytest.mark.parametrize("layer", ["edges", "stations"])
def test_both_networks_load_with_both_layers(place, layer):
    gdf = data.load_network(place, layer=layer)
    assert not gdf.empty
    assert gdf.geometry.notna().all()
    assert gdf.crs is not None


@pytest.mark.parametrize("variant", ["clean", "faulty"])
def test_both_sensor_series_load(variant):
    assert not data.load_sensor_series(variant).empty


@pytest.mark.parametrize("key", sorted(registry.REGISTRY))
def test_describe_reports_a_present_file_for_every_dataset(key):
    text = data.describe(key)
    assert "currently holds" in text, text
    assert "not on this computer" not in text


# STATS19 first_road_class codes -> the prefix the traffic counts use.
ROAD_CLASS_PREFIX = {1: "M", 2: "A", 3: "A", 4: "B", 5: "C", 6: "U"}


def road_key(road_class, road_number):
    """'A58' from (3, 58); 'A1(M)' from (2, 1); 'U' from (6, 0)."""
    prefix = ROAD_CLASS_PREFIX[road_class]
    if road_class == 6:
        return prefix  # every minor road shares one bucket; the number is 0
    # 0 means "unclassified" and -1 "unknown"; neither is a real road number.
    if pd.isna(road_number) or road_number <= 0:
        return prefix
    suffix = "(M)" if road_class == 2 else ""
    return f"{prefix}{road_number}{suffix}"


def road_key_series(collisions):
    return pd.Series(
        [
            road_key(cls, num)
            for cls, num in zip(
                collisions.first_road_class,
                collisions.first_road_number,
                strict=True,
            )
        ],
        index=collisions.index,
    )


def test_major_road_collisions_are_the_joinable_subset():
    c = data.load_collisions()
    major = c.first_road_class.isin([1, 2, 3, 4])
    assert major.sum() == 10_060
    assert (c.first_road_class == 6).sum() == 10_422


def test_a_naive_road_name_join_matches_almost_everything():
    """98.1% matched, which is why the lesson asks whether the number is true."""
    keys = road_key_series(data.load_collisions())
    names = set(data.load_traffic_counts().road_name.dropna())
    assert keys.isin(names).mean() == pytest.approx(0.981, abs=0.001)


def test_the_unclassified_match_is_an_aggregate_bucket_not_a_road():
    """'U' matches on both sides but means 'every minor road', so the rate is void."""
    counts = data.load_traffic_counts()
    assert "U" in set(counts.road_name)
    assert set(counts.loc[counts.road_name == "U", "road_type"]) == {"Minor"}


def test_road_key_never_emits_a_sentinel_or_missing_number():
    for number in (0, -1, pd.NA):
        assert road_key(3, number) == "A"
    assert road_key(6, 0) == "U"
    assert road_key(2, 1) == "A1(M)"


def test_the_casualty_counts_the_lesson_prints_in_its_prose_are_pinned():
    """Two numbers the stage 1 lesson states as text, not as cell output.

    ``notebooks/01-foundations/01-first-look.ipynb`` says "The answer came out
    as 120" of the off-by-one count, and "Nearly twenty times as many cyclists"
    of the fixed one. Both are hard-coded in markdown beside a cell that
    computes them. A rebuild that moved either would leave the page showing one
    number while the prose next to it claimed another, and a beginner has no
    way to tell which to believe.
    """
    casualty_type = data.load_casualties()["casualty_type"]
    # The off-by-one pairing counted code 2 as the cyclists.
    assert (casualty_type == 2).sum() == 120
    # Code 1 is the real cyclists: 19.2 times as many, which is "nearly twenty".
    assert (casualty_type == 1).sum() == 2304
