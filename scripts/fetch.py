"""Download the large upstream source files into a gitignored ``raw/`` directory.

``scripts/build_subsets.py`` and ``scripts/build_osm.py`` cut these into the
small files that are committed under ``data/``. Nothing fetched here is ever
committed. All network access is inside :func:`fetch`.

Usage:
    uv run python scripts/fetch.py                  # everything (about 430 MB)
    uv run python scripts/fetch.py collisions-2024  # just one file
    uv run python scripts/fetch.py --list           # what the names are
    uv run python scripts/fetch.py --force aadf     # re-download, ignoring raw/

Name what you need. The two OpenStreetMap extracts are 164 MB between them, so
refreshing one CSV should not pull them as well.

Run this inside the Codespace, which is hosted outside mainland China. It may
fail on a laptop in Chengdu: the sources live on three hosts,
``data.dft.gov.uk`` (STATS19), ``storage.googleapis.com`` (the AADF zip, DfT's
file CDN on Google Cloud Storage) and ``download.geofabrik.de`` (the
OpenStreetMap extracts); the Google-hosted one in particular is unreliable or
blocked from mainland China. If a download errors or times out, check those
hosts.
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from cwai import registry
from cwai.registry import YEARS

_STATS19 = "https://data.dft.gov.uk/road-accidents-safety-data"
_AADF = (
    "https://storage.googleapis.com/dft-statistics/road-traffic/downloads/data-gov-uk"
)
_GEOFABRIK = "https://download.geofabrik.de"

# Per-year STATS19 files are the narrowest download. DfT publishes them for
# 2021 onwards only, which is what sets cwai.registry.YEARS.
SOURCES: dict[str, str] = {
    f"{table}-{year}": f"{_STATS19}/dft-road-casualty-statistics-{stem}-{year}.csv"
    for table, stem in (
        ("collisions", "collision"),
        ("casualties", "casualty"),
        ("vehicles", "vehicle"),
    )
    for year in YEARS
}
# AADF count-point file, all years, all directions combined (about 19.5 MB).
SOURCES["aadf"] = f"{_AADF}/dft_traffic_counts_aadf.zip"
# Geofabrik regional extracts, the input to scripts/build_osm.py. Geofabrik
# publishes China by province, and Chengdu is in Sichuan; there is no smaller
# extract for either city. These two are 164 MB between them, so fetch them by
# name rather than pulling them to refresh a CSV.
SOURCES["west-yorkshire"] = (
    f"{_GEOFABRIK}/europe/united-kingdom/england/west-yorkshire-latest.osm.pbf"
)
SOURCES["sichuan"] = f"{_GEOFABRIK}/asia/china/sichuan-latest.osm.pbf"

PROVENANCE = "provenance.json"
# Seconds without any data before a connect or read gives up. This is a stall
# detector, not a cap on total time: a slow but moving download is unaffected,
# while a dead connection fails with a visible error instead of hanging.
TIMEOUT = 60


def raw_root() -> Path:
    """The repository's gitignored ``raw/`` directory (it need not exist yet)."""
    return registry.repo_root() / "raw"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(manifest: Path) -> dict:
    return json.loads(manifest.read_text()) if manifest.exists() else {}


def record_provenance(path: Path, manifest: Path, url: str | None = None) -> None:
    """Add or update ``path``'s entry in ``manifest``, keeping other entries."""
    path, manifest = Path(path), Path(manifest)
    entries = _load(manifest)
    entry = {
        "sha256": sha256(path),
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    if url is not None:
        entry["url"] = url
    entries[path.name] = entry
    # Temp file then replace, so an interrupted write cannot corrupt the record.
    partial = manifest.with_name(manifest.name + ".part")
    partial.write_text(json.dumps(entries, indent=2, sort_keys=True) + "\n")
    partial.replace(manifest)


def fetch(name: str, dest_dir: Path, force: bool = False) -> Path:
    """Download source ``name`` into ``dest_dir`` unless already present."""
    url = SOURCES[name]
    dest_dir = Path(dest_dir)
    target = dest_dir / url.rsplit("/", 1)[-1]
    manifest = dest_dir / PROVENANCE
    if target.exists() and not force:
        # Heal a file that arrived but whose provenance was never recorded.
        if target.name not in _load(manifest):
            record_provenance(target, manifest, url=url)
        return target
    dest_dir.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    try:
        with (
            urllib.request.urlopen(url, timeout=TIMEOUT) as response,
            partial.open("wb") as out,
        ):
            while chunk := response.read(1 << 20):
                out.write(chunk)
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
    record_provenance(target, manifest, url=url)
    return target


def _megabytes(size: int) -> str:
    return f"{size / 1024 / 1024:>9.1f} MB"


def main(argv: list[str] | None = None) -> int:
    """Fetch every source, or only the ones named, into ``raw/``."""
    args = list(sys.argv[1:] if argv is None else argv)
    names = [a for a in args if not a.startswith("-")]
    flags = [a for a in args if a.startswith("-")]

    unknown_flags = set(flags) - {"--force", "--list"}
    unknown_names = [n for n in names if n not in SOURCES]
    if unknown_flags or unknown_names:
        for flag in sorted(unknown_flags):
            print(f"unknown option {flag}", file=sys.stderr)
        for name in unknown_names:
            print(f"unknown source {name!r}", file=sys.stderr)
        print(
            "usage: fetch.py [--force] [--list] [NAME ...]\n"
            "names: " + ", ".join(sorted(SOURCES)),
            file=sys.stderr,
        )
        return 2

    if "--list" in flags:
        for name in sorted(SOURCES):
            print(f"{name:<20} {SOURCES[name]}")
        return 0

    wanted = names or sorted(SOURCES)
    dest = raw_root()
    print(f"Fetching {len(wanted)} of {len(SOURCES)} sources into {dest}")
    total = 0
    for name in wanted:
        path = fetch(name, dest, force="--force" in flags)
        size = path.stat().st_size
        total += size
        print(f"{_megabytes(size)}  {path.name}")
    print(f"{_megabytes(total)}  total in {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
