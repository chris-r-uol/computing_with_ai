"""Cut Geofabrik OpenStreetMap extracts down to small central road networks.

OpenStreetMap is the only open source of transport data about Chengdu, so both
cities are built the same way. The expected source files are the Geofabrik
regional extracts, downloaded by hand (the module lead authorises this) into
``raw/``:

* Leeds:    https://download.geofabrik.de/europe/great-britain/england/west-yorkshire-latest.osm.pbf
* Chengdu:  https://download.geofabrik.de/asia/china/sichuan-latest.osm.pbf
  (Geofabrik publishes China by province; Chengdu is in Sichuan.)

Run ``python scripts/build_osm.py leeds raw/west-yorkshire-latest.osm.pbf``
(or ``chengdu raw/sichuan-latest.osm.pbf``). Output paths come from
``cwai.registry``. Each output is a GeoPackage with an ``edges`` layer (roads,
cycleways and footways) and a ``stations`` layer (railway and subway stations),
with an ``ATTRIBUTION.txt`` beside it: the ODbL requires that credit to travel
with the data.

Features that straddle the bounding box are cut at its edge rather than kept
whole or dropped, so the files stay small and the network never extends far
beyond the area named in ``BBOXES``.

Known limitations for graph work
--------------------------------
* Cutting at the edge leaves dangling, unconnected endpoints on the boundary.
* Clipping can turn a road that leaves and re-enters the box into a
  MultiLineString, which some graph code will not accept as one edge.
* The OSM ``lines`` layer carries no node IDs, so a graph must be built by
  snapping coordinates; cut endpoints then become new, isolated nodes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
from shapely.geometry import box

from cwai import registry

# (min_lon, min_lat, max_lon, max_lat), deliberately small central areas.
BBOXES: dict[str, tuple[float, float, float, float]] = {
    "leeds": (-1.62, 53.75, -1.46, 53.84),
    "chengdu": (103.95, 30.60, 104.15, 30.72),
}

HIGHWAY_KEEP: frozenset[str] = frozenset(
    {
        "motorway",
        "trunk",
        "primary",
        "secondary",
        "tertiary",
        "residential",
        "cycleway",
        "footway",
    }
)

# GDAL's OSM driver exposes a .pbf as these layers; the test fixture mimics them.
_LINES_LAYER = "lines"
_POINTS_LAYER = "points"
_STATION_TAGS = (("railway", "station"), ("station", "subway"))

_PLACE_KEYS = {"leeds": "network-leeds", "chengdu": "network-chengdu"}


def _sample(values: pd.Series, n: int = 8) -> list:
    counts = values.value_counts(dropna=False)
    return list(counts.index[:n])


def clip(
    gdf: gpd.GeoDataFrame, bbox: tuple[float, float, float, float]
) -> gpd.GeoDataFrame:
    """Keep the part of each feature inside ``bbox`` (lon/lat), cutting at the edge.

    Raises ``ValueError`` if nothing is left, since an empty network would
    otherwise be written silently.
    """
    window = gpd.GeoSeries([box(*bbox)], crs="EPSG:4326")
    if gdf.crs is not None and gdf.crs != window.crs:
        window = window.to_crs(gdf.crs)
    clipped = gdf.clip(window.iloc[0], keep_geom_type=True)
    clipped = clipped[~clipped.geometry.is_empty].copy()
    if clipped.empty:
        found = (
            tuple(round(float(v), 4) for v in gdf.total_bounds) if len(gdf) else None
        )
        raise ValueError(
            f"Clipping to bbox {bbox} left no features; the input has "
            f"{len(gdf)} features with extent {found}. "
            "Check the extract covers this place."
        )
    return clipped


def _tag(gdf: gpd.GeoDataFrame, key: str) -> pd.Series:
    """Value of an OSM tag, from its own column or the ``other_tags`` hstore."""
    if key in gdf.columns:
        return gdf[key]
    if "other_tags" in gdf.columns:
        extracted = (
            gdf["other_tags"]
            .fillna("")
            .str.extract(rf'"{key}"=>"([^"]*)"', expand=False)
        )
        return extracted
    return pd.Series([None] * len(gdf), index=gdf.index, dtype=object)


def filter_edges(lines: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    highway = _tag(lines, "highway")
    kept = lines[highway.isin(HIGHWAY_KEEP)].copy()
    if kept.empty:
        raise ValueError(
            f"Filtering 'highway' to {sorted(HIGHWAY_KEEP)} left no road "
            f"segments; the values present were {_sample(highway)}."
        )
    kept["highway"] = highway[kept.index]
    return kept


def filter_stations(points: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    mask = pd.Series(False, index=points.index)
    for key, value in _STATION_TAGS:
        mask |= _tag(points, key) == value
    kept = points[mask].copy()
    if kept.empty:
        found = pd.concat([_tag(points, k) for k, _ in _STATION_TAGS]).dropna()
        raise ValueError(
            "Filtering points to railway=station or station=subway left no "
            f"stations; the railway/station values present were {_sample(found)}."
        )
    return kept


def _read(pbf: Path, layer: str, bbox: tuple[float, float, float, float]):
    frame = pyogrio.read_dataframe(pbf, layer=layer, bbox=bbox)
    if frame.empty:
        # Say so here: otherwise the tag filters would blame the tags.
        raise ValueError(
            f"The {layer!r} layer of {pbf} has no features inside bbox {bbox} "
            "and so no features to clip. Check the extract covers this place."
        )
    return frame


def build_network(pbf: Path, place: str, out: Path) -> gpd.GeoDataFrame:
    """Write the ``edges`` and ``stations`` layers for ``place`` to ``out``.

    ``pbf`` is any file GDAL can read with ``lines`` and ``points`` layers, in
    practice a Geofabrik ``.pbf``. Returns the edges.
    """
    if place not in BBOXES:
        raise ValueError(f"Unknown place {place!r}; expected one of {sorted(BBOXES)}.")
    bbox = BBOXES[place]
    # bbox= makes GDAL read only features intersecting the box, so the whole
    # Sichuan extract is never held in memory. It selects, it does not cut: the
    # clip below still trims straddling features.
    lines = _read(pbf, _LINES_LAYER, bbox)
    points = _read(pbf, _POINTS_LAYER, bbox)

    # Filter before clipping so the error names the tags, then clip; either
    # step raising happens before anything is written.
    edges = clip(filter_edges(lines), bbox)
    stations = clip(filter_stations(points), bbox)

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    edges.to_file(out, layer="edges", driver="GPKG")
    stations.to_file(out, layer="stations", driver="GPKG")

    info = registry.get(_PLACE_KEYS[place])
    (out.parent / "ATTRIBUTION.txt").write_text(
        info.attribution + "\n", encoding="utf-8"
    )
    return edges


def build_place(place: str, pbf: Path, root: Path | None = None) -> Path:
    """Build ``place`` at its registry path under ``root`` (default: data dir)."""
    root = registry.data_root() if root is None else Path(root)
    out = root / registry.get(_PLACE_KEYS[place]).relpath
    build_network(pbf, place, out)
    return out


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in BBOXES:
        sys.exit(f"usage: build_osm.py {{{'|'.join(BBOXES)}}} PBF_PATH")
    written = build_place(sys.argv[1], Path(sys.argv[2]))
    print(f"wrote {written} ({written.stat().st_size} bytes)")
