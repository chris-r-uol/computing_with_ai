"""Registry of every vendored dataset: location, licence and attribution.

This module is the single source of truth about the data. Nothing else in the
project should hardcode a data path or an attribution string.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

AREA = "west-yorkshire"
# The span is set by what DfT publishes as per-year STATS19 files (2021 onwards;
# earlier years only come inside multi-gigabyte bundles). Provisional pending a
# decision from the module lead: change it here and nowhere else.
YEARS = (2021, 2022, 2023, 2024, 2025)

ALLOWED_LICENCES = frozenset({"OGL-v3.0", "ODbL-1.0", "CC-BY-SA-4.0", "generated"})

_OGL_ATTRIBUTION = (
    "Contains public sector information licensed under the "
    "Open Government Licence v3.0."
)
_ODBL_ATTRIBUTION = (
    "© OpenStreetMap contributors, licensed under the Open Database License (ODbL)."
)
_STATS19_URL = (
    "https://www.data.gov.uk/dataset/cb7ae6f0-4be6-4935-9277-47e5ce24a11f/"
    "road-accidents-safety-data"
)
_OSM_URL = "https://www.openstreetmap.org/copyright"
_GENERATOR = "scripts/make_synthetic.py"
_GENERATED_ATTRIBUTION = (
    "Generated for this module by scripts/make_synthetic.py; no third-party rights."
)


@dataclass(frozen=True)
class DatasetInfo:
    key: str
    title: str
    relpath: str
    licence: str
    attribution: str
    source_url: str
    description: str


class UnknownDatasetError(KeyError):
    """Raised when a dataset key is not in the registry."""

    def __str__(self) -> str:
        # KeyError would otherwise show the message wrapped in repr quotes.
        return str(self.args[0]) if self.args else ""


def _entries() -> list[DatasetInfo]:
    return [
        DatasetInfo(
            key="collisions",
            title="STATS19 road collisions",
            relpath="stats19/collisions.parquet",
            licence="OGL-v3.0",
            attribution=_OGL_ATTRIBUTION,
            source_url=_STATS19_URL,
            description=(
                "One row per injury road collision reported to the police in West "
                "Yorkshire, with its date, time, location and severity."
            ),
        ),
        DatasetInfo(
            key="casualties",
            title="STATS19 casualties",
            relpath="stats19/casualties.parquet",
            licence="OGL-v3.0",
            attribution=_OGL_ATTRIBUTION,
            source_url=_STATS19_URL,
            description=(
                "One row per person injured in a West Yorkshire collision, giving "
                "their age, sex, road-user type and injury severity; link it to "
                "collisions by collision reference."
            ),
        ),
        DatasetInfo(
            key="vehicles",
            title="STATS19 vehicles",
            relpath="stats19/vehicles.parquet",
            licence="OGL-v3.0",
            attribution=_OGL_ATTRIBUTION,
            source_url=_STATS19_URL,
            description=(
                "One row per vehicle involved in a West Yorkshire collision, with "
                "its type, manoeuvre and driver details; link it to collisions by "
                "collision reference."
            ),
        ),
        DatasetInfo(
            key="traffic-counts",
            title="DfT annual average daily flow (AADF) traffic counts",
            relpath="dft-counts/aadf.parquet",
            licence="OGL-v3.0",
            attribution=_OGL_ATTRIBUTION,
            source_url="https://roadtraffic.dft.gov.uk/downloads",
            description=(
                "Yearly estimates of how many vehicles of each type use each "
                "counted stretch of road on an average day, published by the "
                "Department for Transport. Unlike the collision tables, this "
                "dataset spans every published year rather than only recent "
                "ones: the earlier years give the pre-COVID baseline and the "
                "2020 collapse in traffic, which the collision data cannot show."
            ),
        ),
        DatasetInfo(
            key="network-leeds",
            title="Leeds road network (OpenStreetMap)",
            relpath="osm/leeds.gpkg",
            licence="ODbL-1.0",
            attribution=_ODBL_ATTRIBUTION,
            source_url=_OSM_URL,
            description=(
                "The drivable roads of Leeds as a map file of junctions and road "
                "segments, ready to analyse as a graph."
            ),
        ),
        DatasetInfo(
            key="network-chengdu",
            title="Chengdu road network (OpenStreetMap)",
            relpath="osm/chengdu.gpkg",
            licence="ODbL-1.0",
            attribution=_ODBL_ATTRIBUTION,
            source_url=_OSM_URL,
            description=(
                "The drivable roads of Chengdu, China, in the same format as the "
                "Leeds network so you can compare two very different cities."
            ),
        ),
        DatasetInfo(
            key="sensor-clean",
            title="Synthetic roadside sensor readings (clean)",
            relpath="synthetic/sensor-clean.parquet",
            licence="generated",
            attribution=_GENERATED_ATTRIBUTION,
            source_url=_GENERATOR,
            description=(
                "Made-up but realistic traffic sensor readings over time with "
                "nothing wrong with them, to use as a baseline."
            ),
        ),
        DatasetInfo(
            key="sensor-faulty",
            title="Synthetic roadside sensor readings (faulty)",
            relpath="synthetic/sensor-faulty.parquet",
            licence="generated",
            attribution=_GENERATED_ATTRIBUTION,
            source_url=_GENERATOR,
            description=(
                "The same made-up sensor readings with faults such as stuck "
                "values and dropouts added, for practising anomaly detection."
            ),
        ),
    ]


REGISTRY: dict[str, DatasetInfo] = {info.key: info for info in _entries()}


def get(key: str) -> DatasetInfo:
    """Return the dataset registered under ``key``."""
    try:
        return REGISTRY[key]
    except KeyError:
        available = ", ".join(sorted(REGISTRY))
        raise UnknownDatasetError(
            f"Unknown dataset {key!r}. Available datasets: {available}"
        ) from None


def list_datasets() -> list[DatasetInfo]:
    """Return all registered datasets, sorted by key."""
    return [REGISTRY[key] for key in sorted(REGISTRY)]


def data_root() -> Path:
    """Return the repository's ``data/`` directory (it need not exist yet)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            return parent / "data"
    # Source layout: <repo>/src/cwai/registry.py
    return here.parents[2] / "data"
