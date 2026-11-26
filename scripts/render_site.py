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

from cwai import data, registry

REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = REPO_ROOT / "site"
STUDENT_DIR = REPO_ROOT / "student"
SITE_OUT = Path("_site")
# The module's stage folders; each has a landing page in site/_stages/, and a
# navbar item in site/_quarto.yml pointing at it.
STAGE_DIRS = (
    "00-warmup",
    "01-foundations",
    "02-ai-accelerated",
    "03-machine-learning",
    "04-project",
    "90-stretch",
)

# The eyebrow printed above the title of every page in a stage, including its
# notebooks. It is the plain-text half of the navbar's "you are here": the
# navbar marks the stage with colour and weight, this says it in words, and a
# reader with no JavaScript still gets the second one.
STAGE_EYEBROWS = {
    "00-warmup": "Stage 0",
    "01-foundations": "Stage 1",
    "02-ai-accelerated": "Stage 2",
    "03-machine-learning": "Stage 3",
    "04-project": "Stage 4",
    "90-stretch": "Optional",
}

# Quarto's listing, which is how a notebook is reached now that no sidebar
# lists one. Added only to the stages that have notebooks: an empty listing
# renders an invisible "No matching items" under a heading promising
# notebooks, and warns on every render while it does it.
_LISTING = """listing:
  id: stage-notebooks
  contents: "*.ipynb"
  type: default
  sort: "filename"
  fields: [title, description]
  sort-ui: false
  filter-ui: false
"""

_NOTEBOOK_LIST = """
## Notebooks in this stage

::: {#stage-notebooks}
:::
"""

_NO_NOTEBOOKS = """
::: {.cwai-notice}
**No notebooks here yet.** They appear on this page as they are published, each
one readable in full, with its code and the output of running it.
:::
"""

_LICENCE_NAMES = {
    "OGL-v3.0": "Open Government Licence v3.0",
    "ODbL-1.0": "Open Database License (ODbL) 1.0",
    "CC-BY-SA-4.0": "Creative Commons Attribution-ShareAlike 4.0",
    "generated": "Generated for this module (no third-party rights)",
}


def _source_line(source: str) -> str:
    link = f"[{source}]({source})" if source.startswith("http") else source
    return f"- **Source:** {link}"


def _years_phrase(years: Sequence[int]) -> str:
    """ "2021 to 2025", naming any year missing from inside that span."""
    if len(years) == 1:
        return str(years[0])
    phrase = f"{years[0]} to {years[-1]}"
    gaps = sorted(set(range(years[0], years[-1] + 1)) - set(years))
    if gaps:
        phrase += " (no data for " + ", ".join(str(y) for y in gaps) + ")"
    return phrase


def _years_present(key: str) -> list[int] | None:
    """The years a dataset's file actually holds, or None if it has no years.

    Read from the file rather than asserted, because a sentence asserting a
    span goes stale the moment the data is rebuilt, and the data page is where
    a student goes to find out what they are allowed to conclude.
    """
    try:
        return data.available_years(key)
    except ValueError:
        return None  # not split by year: the networks and the sensor series
    except data.MissingDataError:
        return None  # audited by scripts/check_licences.py, not here


def data_page() -> str:
    """The data page as Quarto markdown, built from the registry and the data."""
    years = {
        key: present
        for key in (i.key for i in registry.list_datasets())
        if (present := _years_present(key))
    }
    spans = sorted({y for present in years.values() for y in present})
    lines = [
        "---",
        "title: Data",
        *_eyebrow_yaml("Reference").rstrip().split("\n"),
        "---",
        "",
        "Every dataset in this module, where it comes from and the licence it is",
        "used under. This page is generated from the dataset registry and from the",
        "data files themselves, so it always matches the data in the repository.",
        "",
    ]
    if spans:
        lines += [
            "The collision and traffic datasets are about "
            f"{registry.AREA.replace('-', ' ').title()} and run from {spans[0]} "
            f"to {spans[-1]}. **They do not all cover the same years**, so check "
            "the years listed under each one before you compare two of them.",
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
        ]
        if info.key in years:
            lines.append(f"- **Years present:** {_years_phrase(years[info.key])}")
        lines.append("")
    return "\n".join(lines)


def _stage_page(source: Path, eyebrow: str, has_notebooks: bool) -> str:
    """A stage landing page, composed from its authored half.

    The authored half is ``site/_stages/<stage>.qmd``: the title and the cards
    that say what the stage covers. The two things added here are the ones that
    depend on what is actually in the folder -- the listing of its notebooks,
    or the note saying there are none yet.

    ``include-before-body`` is set here rather than in the folder's
    ``_metadata.yml`` because a value set in both places does not merge: the
    page's own front matter wins outright, and a stage page that happened to
    need any other before-body content would silently lose its eyebrow.
    """
    text = source.read_text(encoding="utf-8")
    opening, front, body = text.split("---", 2)
    if opening.strip():
        raise ValueError(f"{source}: expected YAML front matter at the top")
    # strip(), not rstrip(): Pandoc reads the front matter only when the first
    # line after the opening fence is YAML, and the split leaves a newline in
    # front of it. A blank line there and the whole block renders as prose, in
    # the middle of the page, which is what it did.
    front = front.strip() + "\n" + _eyebrow_yaml(eyebrow)
    if has_notebooks:
        front += _LISTING
        body = body.strip() + "\n" + _NOTEBOOK_LIST
    else:
        body = body.strip() + "\n" + _NO_NOTEBOOKS
    return f"---\n{front}---\n\n{body}"


def _eyebrow_yaml(eyebrow: str) -> str:
    """The front-matter block that prints the eyebrow above a page's title.

    Quarto puts ``include-before-body`` inside ``<main>`` immediately before
    the title block, which is the one place an eyebrow can go without either a
    template partial or a CSS reordering trick -- and a reordering trick would
    mean a screen reader announcing the title before the label that qualifies
    it.

    A ``<div>`` rather than a ``<p>``, and that is not cosmetic: a listing
    takes an item's description from the first paragraph of the rendered page
    when the document declares none, so as a paragraph the eyebrow became
    every notebook's description -- the stage listing read "Stage 1" under
    every title.
    """
    return (
        "include-before-body:\n"
        "  text: |\n"
        f'    <div class="cwai-eyebrow">{eyebrow}</div>\n'
    )


def _stage_notebooks(site_dir: Path, notebooks: Sequence[Path] | None) -> None:
    """Replace ``site_dir/notebooks`` with copies of the notebooks to publish."""
    target = site_dir / "notebooks"
    if target.exists():
        shutil.rmtree(target)
    for name in STAGE_DIRS:
        # Every stage folder carries its landing page, which is what the
        # navbar item for that stage points at.
        (target / name).mkdir(parents=True)
        # Quarto applies a folder's _metadata.yml to every document in it, so
        # this is what puts the stage's eyebrow above each of its notebooks
        # without touching the notebooks themselves.
        (target / name / "_metadata.yml").write_text(
            _eyebrow_yaml(STAGE_EYEBROWS[name]), encoding="utf-8"
        )
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
    # Last, because each landing page says whether its stage has notebooks yet.
    for name in STAGE_DIRS:
        (target / name / "index.qmd").write_text(
            _stage_page(
                site_dir / "_stages" / f"{name}.qmd",
                STAGE_EYEBROWS[name],
                has_notebooks=any((target / name).glob("*.ipynb")),
            ),
            encoding="utf-8",
        )


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


def main(argv: Sequence[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    # The data page is generated, not committed, so a fresh checkout does not
    # have one. The prose gate checks it like any other page, and a page it
    # cannot find is a failure there rather than a silent pass, so CI writes
    # the page first. A full render would do it too, but it costs a Quarto run
    # of every notebook to produce one file.
    if "--write-data-page" in args:
        page = SITE_DIR / "data.qmd"
        page.write_text(data_page(), encoding="utf-8")
        print(f"Wrote {page}")
        return 0
    done = render(SITE_DIR, REPO_ROOT / SITE_OUT)
    sys.stdout.write(done.stdout)
    sys.stderr.write(done.stderr)
    return done.returncode


if __name__ == "__main__":
    sys.exit(main())
