"""Render the Quarto site from the student notebooks.

The site shows ``student/``, never ``notebooks/``: the student copy has its
solution cells stubbed, so an exercise is still an exercise on first contact.
The full notebooks stay in the repository, and reach the site later through the
``code`` hint tier.

Two things are generated into the Quarto project at render time and are not
committed (``site/data.qmd`` and ``site/notebooks/``), so neither can drift from
its source: the data page comes from the dataset registry, and the notebooks are
copies of whatever is in ``student/``.

Usage:
    uv run python scripts/render_site.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from cwai import registry

REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = REPO_ROOT / "site"
STUDENT_DIR = REPO_ROOT / "student"
SITE_OUT = Path("_site")
# The module's stage folders; each has a landing page in site/stages/.
STAGE_DIRS = (
    "00-warmup",
    "01-foundations",
    "02-ai-accelerated",
    "03-machine-learning",
    "04-project",
    "90-stretch",
)

_LICENCE_NAMES = {
    "OGL-v3.0": "Open Government Licence v3.0",
    "ODbL-1.0": "Open Database License (ODbL) 1.0",
    "CC-BY-SA-4.0": "Creative Commons Attribution-ShareAlike 4.0",
    "generated": "Generated for this module (no third-party rights)",
}


def _source_line(source: str) -> str:
    link = f"[{source}]({source})" if source.startswith("http") else source
    return f"- **Source:** {link}"


def data_page() -> str:
    """The data page as Quarto markdown, built from the registry."""
    lines = [
        "---",
        "title: Data",
        "---",
        "",
        "Every dataset in this module, where it comes from and the licence it is",
        "used under. This page is generated from the dataset registry, so it always",
        "matches the data in the repository.",
        "",
        f"The real datasets cover {registry.AREA.replace('-', ' ').title()}, "
        f"{registry.YEARS[0]} to {registry.YEARS[-1]}.",
        "",
    ]
    for info in registry.list_datasets():
        licence = _LICENCE_NAMES.get(info.licence, info.licence)
        lines += [
            f"## {info.title}",
            "",
            info.description,
            "",
            f"- **Licence:** {licence}",
            f"- **Attribution:** {info.attribution}",
            _source_line(info.source_url),
            "",
        ]
    return "\n".join(lines)


def _stage_notebooks(site_dir: Path, notebooks: Sequence[Path] | None) -> None:
    """Replace ``site_dir/notebooks`` with copies of the notebooks to publish."""
    target = site_dir / "notebooks"
    if target.exists():
        shutil.rmtree(target)
    for name in STAGE_DIRS:
        # Quarto's sidebar globbing fails on an empty folder, so every stage
        # folder carries its landing page.
        (target / name).mkdir(parents=True)
        shutil.copy2(site_dir / "_stages" / f"{name}.qmd", target / name / "index.qmd")
    if notebooks is None:
        notebooks = sorted(
            p
            for p in STUDENT_DIR.rglob("*.ipynb")
            if ".ipynb_checkpoints" not in p.parts
        )
    for path in notebooks:
        path = Path(path).resolve()
        # Keep the stage folder for student notebooks; anything else is placed flat.
        rel = (
            path.relative_to(STUDENT_DIR)
            if path.is_relative_to(STUDENT_DIR)
            else (Path(path.name))
        )
        if len(rel.parts) == 1:
            rel = Path("90-stretch") / rel
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)


def _quarto() -> str:
    beside_python = Path(sys.executable).parent / "quarto"
    if beside_python.exists():
        return str(beside_python)
    found = shutil.which("quarto")
    if found is None:
        raise FileNotFoundError("quarto not found; run `uv sync --all-groups`")
    return found


def render(
    site_dir: Path, out_dir: Path, notebooks: Sequence[Path] | None = None
) -> subprocess.CompletedProcess:
    """Render the site; return the finished process rather than raising.

    ``notebooks`` restricts the published notebooks to a subset (the default is
    everything under ``student/``). A notebook that errors when executed fails
    the render, so it cannot reach a published page.
    """
    site_dir = Path(site_dir)
    (site_dir / "data.qmd").write_text(data_page(), encoding="utf-8")
    _stage_notebooks(site_dir, notebooks)
    # Quarto's Jupyter engine must use this interpreter, not whatever is first on PATH.
    env = {**os.environ, "QUARTO_PYTHON": sys.executable}
    return subprocess.run(
        [
            _quarto(),
            "render",
            str(site_dir),
            "--output-dir",
            str(Path(out_dir).resolve()),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def main() -> int:
    done = render(SITE_DIR, REPO_ROOT / SITE_OUT)
    sys.stdout.write(done.stdout)
    sys.stderr.write(done.stderr)
    return done.returncode


if __name__ == "__main__":
    sys.exit(main())
