"""Build the site's Tailwind stylesheet, and check the committed copy is fresh.

``site/tailwind.css`` is a build artefact that is nevertheless committed, because
a student's browser must not have to fetch Tailwind from a CDN: ``cdn.tailwindcss
.com`` is a browser-side JIT build, and it would put a blocking third-party
request on the critical path of a site whose whole point includes being readable
from Chengdu on a poor connection.

A committed generated file with no freshness check is a trap, so this script
also runs the build in reverse. ``--check`` rebuilds into a temporary directory
and compares bytes with the committed file, which is the same contract
``scripts/build_student_notebooks.py --check`` has for ``student/``. It is wired
into ``.github/workflows/checks.yml``, so every path that publishes or merges
proves the stylesheet matches its source.

The Tailwind version is pinned. With ``latest``, the same inputs would produce
different output the day Tailwind cut a release, and the check would fail on a
pull request that touched nothing.

Usage:
    uv run python scripts/build_tailwind.py            # rebuild
    uv run python scripts/build_tailwind.py --check    # fail if stale
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

import pytailwindcss
from pytailwindcss.exceptions import PyTailwindCssException

REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = REPO_ROOT / "site"
TAILWIND_DIR = SITE_DIR / "_tailwind"
# Underscore-prefixed, so Quarto ignores the source files and renders neither.
CONFIG = TAILWIND_DIR / "tailwind.config.js"
INPUT_CSS = TAILWIND_DIR / "input.css"
OUTPUT_CSS = SITE_DIR / "tailwind.css"

# Pinned deliberately; see the module docstring. Tailwind 3 is what the
# `corePlugins: { preflight: false }` switch in tailwind.config.js belongs to:
# Tailwind 4 removed `corePlugins` altogether, and turning preflight off there
# means hand-assembling the `@import`s instead.
TAILWIND_VERSION = "v3.4.17"

BANNER = f"""\
/* GENERATED FILE -- DO NOT EDIT.
 *
 * Built from site/_tailwind/input.css and site/_tailwind/tailwind.config.js by
 * Tailwind CSS {TAILWIND_VERSION}, via:
 *
 *     uv run python scripts/build_tailwind.py
 *
 * CI rebuilds this and fails if it differs from the committed copy, so an edit
 * made here is lost at the next build and blocks the pull request meanwhile.
 * Edit site/_tailwind/input.css instead.
 */
"""


class TailwindBuildError(RuntimeError):
    """The Tailwind CLI could not be obtained or could not build the input."""


def build(out_path: Path) -> bytes:
    """Compile the design layer to ``out_path`` and return the bytes written."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    args = [
        "--config",
        str(CONFIG.relative_to(REPO_ROOT)),
        "--input",
        str(INPUT_CSS.relative_to(REPO_ROOT)),
        "--output",
        str(out_path),
    ]
    try:
        pytailwindcss.run(
            args,
            cwd=REPO_ROOT,
            version=TAILWIND_VERSION,
            auto_install=True,
        )
    except PyTailwindCssException as exc:
        raise TailwindBuildError(str(exc)) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or b"").decode(errors="replace").strip()
        raise TailwindBuildError(f"tailwindcss failed:\n{detail}") from exc

    # The banner is prepended here rather than kept in input.css, where Tailwind
    # would hoist it below its own version comment and a reader opening the
    # generated file would not see the warning first.
    written = BANNER.encode() + out_path.read_bytes()
    out_path.write_bytes(written)
    return written


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="write nothing; exit 1 if site/tailwind.css is out of date",
    )
    args = parser.parse_args(argv)

    try:
        if args.check:
            return _check()
        build(OUTPUT_CSS)
    except TailwindBuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {OUTPUT_CSS.relative_to(REPO_ROOT)}")
    return 0


def _check() -> int:
    if not OUTPUT_CSS.exists():
        print(f"missing: {OUTPUT_CSS.relative_to(REPO_ROOT)}")
        print("Run: uv run python scripts/build_tailwind.py")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        fresh = build(Path(tmp) / "tailwind.css")
    if fresh != OUTPUT_CSS.read_bytes():
        print(f"out of date: {OUTPUT_CSS.relative_to(REPO_ROOT)}")
        print("Run: uv run python scripts/build_tailwind.py")
        return 1
    print(f"up to date: {OUTPUT_CSS.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
