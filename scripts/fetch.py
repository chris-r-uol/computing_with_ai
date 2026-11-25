"""Download the large upstream DfT files into a gitignored ``raw/`` directory.

Task 5 cuts these into the small subsets that are committed. Nothing fetched
here is ever committed. All network access is inside :func:`fetch`.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from cwai.registry import YEARS

_STATS19 = "https://data.dft.gov.uk/road-accidents-safety-data"
_AADF = "https://storage.googleapis.com/dft-statistics/road-traffic/downloads/data-gov-uk"

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

PROVENANCE = "provenance.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record_provenance(path: Path, manifest: Path, url: str | None = None) -> None:
    """Add or update ``path``'s entry in ``manifest``, keeping other entries."""
    path, manifest = Path(path), Path(manifest)
    entries = json.loads(manifest.read_text()) if manifest.exists() else {}
    entry = {
        "sha256": sha256(path),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if url is not None:
        entry["url"] = url
    entries[path.name] = entry
    manifest.write_text(json.dumps(entries, indent=2, sort_keys=True) + "\n")


def fetch(name: str, dest_dir: Path, force: bool = False) -> Path:
    """Download source ``name`` into ``dest_dir`` unless already present."""
    url = SOURCES[name]
    dest_dir = Path(dest_dir)
    target = dest_dir / url.rsplit("/", 1)[-1]
    if target.exists() and not force:
        return target
    dest_dir.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    try:
        with urllib.request.urlopen(url) as response, partial.open("wb") as out:
            while chunk := response.read(1 << 20):
                out.write(chunk)
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
    record_provenance(target, dest_dir / PROVENANCE, url=url)
    return target
