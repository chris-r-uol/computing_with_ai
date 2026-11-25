import geopandas as gpd
import pyogrio
import pytest
from build_osm import BBOXES, HIGHWAY_KEEP, build_network, build_place, clip
from shapely.geometry import LineString, Point

from cwai import registry

LEEDS = BBOXES["leeds"]  # (-1.62, 53.75, -1.46, 53.84)


def _lines():
    return gpd.GeoDataFrame(
        {"name": ["inside", "cornwall", "straddle"]},
        geometry=[
            LineString([(-1.55, 53.79), (-1.54, 53.80)]),
            LineString([(-5.05, 50.15), (-5.04, 50.16)]),
            LineString([(-1.50, 53.80), (-1.30, 53.80)]),  # leaves east edge
        ],
        crs="EPSG:4326",
    )


def test_clip_keeps_inside_drops_outside():
    out = clip(_lines(), LEEDS)
    assert set(out["name"]) == {"inside", "straddle"}


def test_clip_cuts_straddling_feature_at_the_edge():
    out = clip(_lines(), LEEDS).set_index("name")
    assert out.loc["straddle"].geometry.bounds[2] == pytest.approx(LEEDS[2])
    assert out.loc["inside"].geometry.length == pytest.approx(
        _lines().geometry.iloc[0].length
    )


def test_clip_preserves_crs():
    gdf = _lines()
    assert clip(gdf, LEEDS).crs == gdf.crs


def test_clip_raises_when_nothing_inside():
    far = _lines().iloc[[1]]
    with pytest.raises(ValueError, match="no features") as exc:
        clip(far, LEEDS)
    assert "-5.0" in str(exc.value)


def _make_fixture(path, highways=("primary", "residential", "service", "primary")):
    """A tiny GeoPackage with the layers and columns GDAL's OSM driver gives."""
    geoms = [
        LineString([(-1.55, 53.79), (-1.54, 53.80)]),
        LineString([(-1.53, 53.79), (-1.52, 53.78)]),
        LineString([(-1.51, 53.79), (-1.50, 53.80)]),
        LineString([(-5.05, 50.15), (-5.04, 50.16)]),  # Cornwall
    ]
    lines = gpd.GeoDataFrame(
        {"highway": list(highways), "other_tags": [None] * 4},
        geometry=geoms,
        crs="EPSG:4326",
    )
    points = gpd.GeoDataFrame(
        {
            "name": ["Leeds", "Shop", "Metro", "Truro"],
            "other_tags": [
                '"railway"=>"station"',
                '"shop"=>"bakery"',
                '"station"=>"subway"',
                '"railway"=>"station"',
            ],
        },
        geometry=[
            Point(-1.548, 53.795),
            Point(-1.55, 53.80),
            Point(-1.52, 53.79),
            Point(-5.05, 50.15),
        ],
        crs="EPSG:4326",
    )
    lines.to_file(path, layer="lines", driver="GPKG")
    points.to_file(path, layer="points", driver="GPKG")


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "source.gpkg"
    _make_fixture(path)
    return path


def test_output_has_edges_and_stations_layers(tmp_path, source):
    out = tmp_path / "osm" / "leeds.gpkg"
    build_network(source, "leeds", out)
    assert {name for name, _ in pyogrio.list_layers(out)} == {"edges", "stations"}


def test_only_kept_highways_and_stations_inside_bbox(tmp_path, source):
    out = tmp_path / "leeds.gpkg"
    build_network(source, "leeds", out)
    edges = pyogrio.read_dataframe(out, layer="edges")
    stations = pyogrio.read_dataframe(out, layer="stations")
    assert sorted(edges["highway"]) == ["primary", "residential"]
    assert set(edges["highway"]) <= HIGHWAY_KEEP
    # shop is not a station; Truro is a station but outside Leeds
    assert sorted(stations["name"]) == ["Leeds", "Metro"]


def test_attribution_written_alongside_output(tmp_path, source):
    out = tmp_path / "osm" / "leeds.gpkg"
    build_network(source, "leeds", out)
    text = (out.parent / "ATTRIBUTION.txt").read_text(encoding="utf-8")
    assert "OpenStreetMap contributors" in text
    assert registry.get("network-leeds").attribution in text


def test_unwanted_highways_raise_and_write_nothing(tmp_path):
    src = tmp_path / "bad.gpkg"
    _make_fixture(src, highways=("service", "track", "path", "service"))
    out = tmp_path / "leeds.gpkg"
    with pytest.raises(ValueError, match="highway") as exc:
        build_network(src, "leeds", out)
    assert "service" in str(exc.value)
    assert not out.exists()


def test_wrong_place_for_extract_raises_before_writing(tmp_path, source):
    out = tmp_path / "chengdu.gpkg"
    with pytest.raises(ValueError, match="no features"):
        build_network(source, "chengdu", out)
    assert not out.exists()


def test_build_place_uses_registry_path(tmp_path, source):
    out = build_place("leeds", source, root=tmp_path)
    assert out == tmp_path / registry.get("network-leeds").relpath
    assert out.exists()
