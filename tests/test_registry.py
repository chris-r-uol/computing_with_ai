from pathlib import Path

import pytest

from cwai import registry

OGL = (
    "Contains public sector information licensed under the "
    "Open Government Licence v3.0."
)
ODBL = "© OpenStreetMap contributors, licensed under the Open Database License (ODbL)."

EXPECTED_RELPATHS = {
    "collisions": "stats19/collisions.parquet",
    "casualties": "stats19/casualties.parquet",
    "vehicles": "stats19/vehicles.parquet",
    "traffic-counts": "dft-counts/aadf.parquet",
    "network-leeds": "osm/leeds.gpkg",
    "network-chengdu": "osm/chengdu.gpkg",
    "sensor-clean": "synthetic/sensor-clean.parquet",
    "sensor-faulty": "synthetic/sensor-faulty.parquet",
}


def test_every_entry_declares_licence_and_attribution():
    for info in registry.list_datasets():
        assert info.licence in registry.ALLOWED_LICENCES
        assert info.attribution.strip()
        assert info.source_url.strip()
        assert info.description.strip()


def test_keys_match_mapping_keys():
    for key, info in registry.REGISTRY.items():
        assert info.key == key


def test_get_unknown_key_lists_available_keys():
    with pytest.raises(registry.UnknownDatasetError) as exc:
        registry.get("no-such-dataset")
    assert "collisions" in str(exc.value)


def test_unknown_dataset_error_is_a_key_error():
    with pytest.raises(KeyError):
        registry.get("no-such-dataset")


def test_ogl_entries_carry_exact_attribution_string():
    for info in registry.list_datasets():
        if info.licence == "OGL-v3.0":
            assert info.attribution == OGL


def test_odbl_entries_carry_exact_attribution_string():
    for info in registry.list_datasets():
        if info.licence == "ODbL-1.0":
            assert info.attribution == ODBL


def test_relpaths_are_fixed():
    assert {k: v.relpath for k, v in registry.REGISTRY.items()} == EXPECTED_RELPATHS


def test_licence_assignment_and_allowed_set():
    assert registry.ALLOWED_LICENCES == {
        "OGL-v3.0",
        "ODbL-1.0",
        "CC-BY-SA-4.0",
        "generated",
    }
    assert {k for k, v in registry.REGISTRY.items() if v.licence == "generated"} == {
        "sensor-clean",
        "sensor-faulty",
    }
    assert registry.get("network-leeds").licence == "ODbL-1.0"
    assert registry.get("traffic-counts").licence == "OGL-v3.0"


def test_source_urls():
    stats19 = (
        "https://www.data.gov.uk/dataset/cb7ae6f0-4be6-4935-9277-47e5ce24a11f/"
        "road-accidents-safety-data"
    )
    for key in ("collisions", "casualties", "vehicles"):
        assert registry.get(key).source_url == stats19
    assert (
        registry.get("traffic-counts").source_url
        == "https://roadtraffic.dft.gov.uk/downloads"
    )
    for key in ("network-leeds", "network-chengdu"):
        assert registry.get(key).source_url == "https://www.openstreetmap.org/copyright"
    for key in ("sensor-clean", "sensor-faulty"):
        assert registry.get(key).source_url == "scripts/make_synthetic.py"


def test_list_datasets_sorted_by_key():
    keys = [d.key for d in registry.list_datasets()]
    assert keys == sorted(keys)
    assert len(keys) == 8


def test_dataset_info_is_frozen():
    with pytest.raises(AttributeError):
        registry.get("collisions").title = "x"


def test_area_and_years():
    assert registry.AREA == "west-yorkshire"
    assert registry.YEARS == (2021, 2022, 2023, 2024, 2025)


def test_data_root_is_repo_data_dir_and_need_not_exist():
    root = registry.data_root()
    assert isinstance(root, Path)
    assert root.name == "data"
    assert (root.parent / "pyproject.toml").is_file()


def test_repo_root_is_found_by_walking_up_not_by_counting():
    root = registry.repo_root()
    assert (root / "pyproject.toml").is_file()
    assert registry.data_root() == root / "data"


def test_everything_that_needs_the_repo_root_agrees_on_it():
    """One way up to the repository root, not a fixed parents[] index per module."""
    import fetch

    from cwai import checks

    root = registry.repo_root()
    assert checks._EXPECTED_PATH == root / "checks" / "expected.json"
    assert fetch.raw_root() == root / "raw"
