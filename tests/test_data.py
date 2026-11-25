from pathlib import Path

import geopandas as gpd
import pytest
from build_subsets import (
    build_casualties,
    build_collisions,
    build_counts,
    build_vehicles,
)
from shapely.geometry import LineString, Point

from cwai import registry
from cwai.data import (
    MissingDataError,
    YearNotAvailableError,
    available_years,
    describe,
    load_casualties,
    load_collisions,
    load_network,
    load_sensor_series,
    load_traffic_counts,
    load_vehicles,
)
from cwai.registry import YEARS

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE = FIXTURES / "stats19_collisions_sample.csv"
CASUALTIES = FIXTURES / "stats19_casualties_sample.csv"
VEHICLES = FIXTURES / "stats19_vehicles_sample.csv"
COUNTS = FIXTURES / "dft_counts_sample.csv"


def _place(root, key):
    path = root / registry.get(key).relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """A data tree built from the CSV fixtures, laid out at the registry paths."""
    root = tmp_path / "data"
    build_collisions(FIXTURE, _place(root, "collisions"))
    build_casualties(CASUALTIES, _place(root, "casualties"))
    build_vehicles(VEHICLES, _place(root, "vehicles"))
    build_counts(COUNTS, _place(root, "traffic-counts"))
    for place in ("leeds", "chengdu"):
        gpkg = _place(root, f"network-{place}")
        edges = gpd.GeoDataFrame(
            {"name": ["A", "B"]},
            geometry=[LineString([(0, 0), (1, 1)]), LineString([(1, 1), (2, 0)])],
            crs="EPSG:4326",
        )
        stations = gpd.GeoDataFrame(
            {"name": ["S"]}, geometry=[Point(0, 0)], crs="EPSG:4326"
        )
        edges.to_file(gpkg, layer="edges", driver="GPKG")
        stations.to_file(gpkg, layer="stations", driver="GPKG")
    monkeypatch.setattr(registry, "data_root", lambda: root)
    return root


def test_fixture_tree_covers_every_year(tree):
    # Without this the default-span test below would assert nothing.
    assert YEARS == (2021, 2022, 2023, 2024, 2025)
    assert available_years("collisions") == list(YEARS)


def test_load_collisions_returns_all_years_by_default(tree):
    assert set(load_collisions().accident_year) == set(YEARS)


def test_load_collisions_filters_to_requested_years(tree):
    assert set(load_collisions(years=[2022]).accident_year) == {2022}


def test_a_single_int_year_is_accepted(tree):
    assert set(load_collisions(years=2022).accident_year) == {2022}


def test_severity_label_survives_loading(tree):
    assert list(load_collisions().severity_label.cat.categories) == [
        "Fatal",
        "Serious",
        "Slight",
    ]


@pytest.mark.parametrize(
    ("loader", "key"),
    [
        (load_casualties, "casualties"),
        (load_vehicles, "vehicles"),
        (load_traffic_counts, "traffic-counts"),
    ],
)
def test_other_tabular_loaders_filter_and_guard_years(tree, loader, key):
    year = available_years(key)[0]
    column = "year" if key == "traffic-counts" else "accident_year"
    assert set(loader(years=[year])[column]) == {year}
    with pytest.raises(YearNotAvailableError):
        loader(years=[1999])


def test_requesting_absent_year_raises_and_lists_available(tree):
    with pytest.raises(YearNotAvailableError) as exc:
        load_collisions(years=[1999])
    msg = str(exc.value)
    assert "1999" in msg
    for year in YEARS:
        assert str(year) in msg


def test_one_absent_year_among_valid_ones_still_raises(tree):
    # Partial matches must not quietly return only the years that exist.
    with pytest.raises(YearNotAvailableError) as exc:
        load_collisions(years=[2022, 1999])
    assert "1999" in str(exc.value)


def test_empty_years_list_raises_rather_than_returning_nothing(tree):
    with pytest.raises(YearNotAvailableError):
        load_collisions(years=[])


def test_missing_file_raises_actionable_message(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "data_root", lambda: tmp_path)
    with pytest.raises(MissingDataError) as exc:
        load_collisions()
    msg = str(exc.value)
    assert "collisions" in msg
    assert "scripts/build_subsets.py" in msg


def test_missing_error_is_a_file_not_found_error(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "data_root", lambda: tmp_path)
    with pytest.raises(FileNotFoundError):
        load_traffic_counts()


@pytest.mark.parametrize(
    ("call", "script"),
    [
        (lambda: load_network("chengdu"), "scripts/build_osm.py"),
        (lambda: load_sensor_series("faulty"), "scripts/make_synthetic.py"),
    ],
)
def test_missing_message_names_the_right_script_per_dataset(
    tmp_path, monkeypatch, call, script
):
    monkeypatch.setattr(registry, "data_root", lambda: tmp_path)
    with pytest.raises(MissingDataError, match=script):
        call()


def test_load_network_reads_each_layer(tree):
    edges = load_network()
    assert isinstance(edges, gpd.GeoDataFrame) and len(edges) == 2
    assert len(load_network("chengdu", layer="stations")) == 1


def test_unknown_network_place_lists_available_places():
    with pytest.raises(registry.UnknownDatasetError) as exc:
        load_network(place="paris")
    assert "leeds" in str(exc.value) and "chengdu" in str(exc.value)


def test_unknown_network_layer_lists_available_layers(tree):
    with pytest.raises(ValueError) as exc:
        load_network(layer="roads")
    assert "edges" in str(exc.value) and "stations" in str(exc.value)


def test_unknown_sensor_variant_lists_options():
    with pytest.raises(ValueError) as exc:
        load_sensor_series("broken")
    assert "clean" in str(exc.value) and "faulty" in str(exc.value)


def test_sensor_variants_differ():
    assert load_sensor_series("clean").flow.isna().sum() == 0
    assert load_sensor_series("faulty").flow.isna().sum() > 0


def test_available_years_rejects_datasets_not_split_by_year(tree):
    with pytest.raises(ValueError, match="collisions"):
        available_years("network-leeds")


def test_describe_includes_licence_and_attribution(tree):
    text = describe("collisions")
    assert "Open Government Licence" in text
    assert registry.get("collisions").attribution in text
    assert "2021 to 2025" in text
    assert f"{len(load_collisions()):,} rows" in text


def test_describe_counts_network_edges(tree):
    assert "2 rows" in describe("network-leeds")


def test_describe_still_works_when_data_not_built(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "data_root", lambda: tmp_path)
    text = describe("collisions")
    assert "not been built" in text and "Open Government Licence" in text


def test_describe_unknown_key_lists_datasets():
    with pytest.raises(registry.UnknownDatasetError):
        describe("nope")
