"""Serve the two scripts Quarto's Jupyter engine injects from this site, not a CDN.

Quarto adds ``jquery`` and ``requirejs`` to any notebook page that has an HTML or
JavaScript output (a pandas table is enough), and it loads both from
``cdn.jsdelivr.net``. There is no Quarto setting that turns this off: the choice
is made in ``includesForJupyterWidgetDependencies`` and is keyed to the notebook's
output types, not to anything in ``_quarto.yml``. jsDelivr lost its mainland China
ICP licence in 2021 and is unreliable from Chengdu, and a notebook page is the
page a student opens when their Codespace will not connect, so the degraded-mode
path would carry two blocking third-party requests.

So the files are vendored under ``site/vendor/`` (versions, hashes and licences
below and in ``site/vendor/NOTICE.txt``) and this script rewrites each rendered
page to point at them. It is wired in as the project's ``post-render`` step in
``site/_quarto.yml``, so it runs however the site is rendered
(``scripts/render_site.py``, ``uv run quarto render site`` or ``quarto preview``).

The rewrite is idempotent and touches nothing but those two ``<script>`` tags. It
also drops their ``integrity`` and ``crossorigin`` attributes: the hashes Quarto
writes belong to the CDN copy, and a same-origin file needs neither. The vendored
bytes are instead pinned by SHA-256 here, which ``--check`` verifies in CI.

Anything else third-party is deliberately not rewritten: it should fail
``tests/test_site.py::test_pages_fetch_no_third_party_resource`` and be a decision.

Standard library only, because Quarto runs post-render scripts with whatever
``python3`` is on the PATH.

To update a library: download the new file, replace the entry below (version,
URL, hashes), rename the file under ``site/vendor/``, and update ``NOTICE.txt``.

Usage:
    uv run python scripts/selfhost_assets.py --check          # verify vendored files
    uv run python scripts/selfhost_assets.py --output-dir D   # rewrite a rendered site
    (Quarto runs the rewrite itself via QUARTO_PROJECT_OUTPUT_DIR.)
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = REPO_ROOT / "site"
VENDOR_DIRNAME = "vendor"
VENDOR_DIR = SITE_DIR / VENDOR_DIRNAME
NOTICE = VENDOR_DIR / "NOTICE.txt"


@dataclass(frozen=True)
class Asset:
    """One vendored file and the CDN URL Quarto would otherwise have loaded."""

    filename: str
    cdn_url: str
    version: str
    sha256: str
    licence: str
    # A fragment of the library's own banner, which must survive in the file:
    # for a minified file the banner is the licence notice.
    banner: str


ASSETS = (
    Asset(
        filename="jquery-3.5.1.min.js",
        cdn_url="https://cdn.jsdelivr.net/npm/jquery@3.5.1/dist/jquery.min.js",
        version="3.5.1",
        sha256="f7f6a5894f1d19ddad6fa392b2ece2c5e578cbf7da4ea805b6885eb6985b6e3d",
        licence="MIT",
        banner=(
            "jQuery v3.5.1 | (c) JS Foundation and other contributors"
            " | jquery.org/license"
        ),
    ),
    Asset(
        filename="require-2.3.6.min.js",
        cdn_url="https://cdn.jsdelivr.net/npm/requirejs@2.3.6/require.min.js",
        version="2.3.6",
        sha256="08820fe928391c47d804d54b5ee8f07f7c1eda5df6ab5da99c3c32b494563962",
        licence="MIT",
        banner=(
            "@license RequireJS 2.3.6 Copyright jQuery Foundation"
            " and other contributors."
        ),
    ),
)

_SCRIPT_TAG = re.compile(r"<script\b[^>]*>", re.IGNORECASE)
_SRC_ATTR = re.compile(r'\bsrc="([^"]*)"')
# Whole attribute, with its leading space, so removal leaves a well-formed tag.
_DROPPED_ATTRS = re.compile(r'\s+(?:integrity|crossorigin)(?:="[^"]*")?', re.IGNORECASE)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(vendor_dir: Path = VENDOR_DIR) -> list[str]:
    """Return problems with the vendored files; empty when they are as pinned."""
    problems: list[str] = []
    notice = vendor_dir / NOTICE.name
    notice_text = notice.read_text(encoding="utf-8") if notice.exists() else ""
    if not notice_text:
        problems.append(f"{notice} is missing; vendored files need a licence note.")
    for asset in ASSETS:
        path = vendor_dir / asset.filename
        if not path.exists():
            problems.append(f"{path} is missing.")
            continue
        if sha256_of(path) != asset.sha256:
            problems.append(
                f"{path} does not match the SHA-256 pinned in "
                "scripts/selfhost_assets.py; if you changed it on purpose, update "
                "the pin, the version and NOTICE.txt together."
            )
        if asset.banner not in path.read_text(encoding="utf-8"):
            problems.append(f"{path} has lost its licence banner ({asset.banner!r}).")
        if notice_text and not (
            asset.filename in notice_text
            and asset.version in notice_text
            and asset.sha256 in notice_text
            and asset.licence in notice_text
        ):
            problems.append(
                f"{notice} does not record {asset.filename} "
                "(version, licence and SHA-256)."
            )
    return problems


def rewrite_html(html: str, page: Path, out_dir: Path) -> str:
    """Point the CDN ``<script>`` tags in ``html`` at the vendored copies."""
    by_url = {asset.cdn_url: asset for asset in ASSETS}
    page_dir = page.parent

    def swap(match: re.Match[str]) -> str:
        tag = match.group(0)
        src = _SRC_ATTR.search(tag)
        asset = by_url.get(src.group(1)) if src else None
        if asset is None:
            return tag
        local = out_dir / VENDOR_DIRNAME / asset.filename
        if not local.exists():
            raise FileNotFoundError(
                f"{local} is missing from the rendered site; "
                f"site/{VENDOR_DIRNAME}/ should be copied there by Quarto."
            )
        relative = Path(os.path.relpath(local, page_dir)).as_posix()
        tag = _DROPPED_ATTRS.sub("", tag)
        return _SRC_ATTR.sub(f'src="{relative}"', tag, count=1)

    return _SCRIPT_TAG.sub(swap, html)


def rewrite_site(out_dir: Path) -> int:
    """Rewrite every rendered page under ``out_dir``; return pages changed."""
    changed = 0
    for page in sorted(out_dir.rglob("*.html")):
        before = page.read_text(encoding="utf-8")
        after = rewrite_html(before, page, out_dir)
        if after != before:
            page.write_text(after, encoding="utf-8")
            changed += 1
    return changed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="verify vendored files")
    parser.add_argument("--output-dir", type=Path, help="a rendered site to rewrite")
    args = parser.parse_args(argv)

    if args.check:
        problems = check()
        for problem in problems:
            print(f"selfhost_assets: {problem}", file=sys.stderr)
        if not problems:
            print(f"selfhost_assets: {len(ASSETS)} vendored files match their pins.")
        return 1 if problems else 0

    out_dir = args.output_dir or os.environ.get("QUARTO_PROJECT_OUTPUT_DIR")
    if not out_dir:
        parser.error("give --output-dir, or run as a Quarto post-render step")
    changed = rewrite_site(Path(out_dir).resolve())
    print(f"selfhost_assets: rewrote the CDN scripts on {changed} page(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
