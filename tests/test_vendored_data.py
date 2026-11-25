"""Assertions about the data that is actually committed under ``data/``.

Every other test in the suite runs against hand-written CSV fixtures, so a
truncated, mis-columned or wrong-year ``collisions.parquet`` would keep the
whole suite green while every notebook built on it was wrong. These tests load
the committed files themselves, through the same loaders a student uses.

They are the only tests that fail when the data is rebuilt badly, so keep them
about the data's shape and coverage rather than its exact row counts, which
change at every upstream refresh.
"""

from __future__ import annotations

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
