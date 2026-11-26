"""The workbook template: the file a student grows all week.

It lives under ``notebooks/`` so CI runs it, but it is the student's own file.
It is not a lesson, so nothing in it is stripped, checked or graded.
"""

import re
from pathlib import Path

import check_prose
import nbformat
import pytest
import run_notebooks
from build_student_notebooks import (
    TEMPLATE_NAME,
    build,
    stale_paths,
)
from nbclient import NotebookClient

from cwai import slices

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "notebooks" / "04-project" / "my-analysis-template.ipynb"
SECTIONS = (
    "slice",
    "first look",
    "cleaning",
    "description",
    "join",
    "rate",
    "not show",
)


def load_template():
    return nbformat.read(TEMPLATE, as_version=4)


def headings(nb):
    return [
        line.lstrip("# ").strip()
        for cell in nb.cells
        if cell.cell_type == "markdown"
        for line in cell.source.splitlines()
        if line.startswith("## ")
    ]


def tags(cell):
    return set(cell.get("metadata", {}).get("tags", []))


@pytest.fixture(scope="module")
def executed():
    """The template run once on a fresh kernel, so tests can read its output."""
    nb = load_template()
    NotebookClient(
        nb,
        timeout=run_notebooks.TIMEOUT_SECONDS,
        kernel_name="python3",
        resources={"metadata": {"path": str(REPO)}},
    ).execute()
    return nb


def test_the_template_has_every_section_the_design_names():
    found = [h.lower() for h in headings(load_template())]
    for section in SECTIONS:
        assert any(section in h for h in found), section
    assert len(found) == len(SECTIONS)


def test_the_template_runs_on_a_fresh_kernel():
    """It must work the moment a student copies it, before they write anything."""
    result = run_notebooks.run(TEMPLATE)
    assert result.passed, result.error
    assert result.seconds < 120


def test_every_section_ends_in_an_empty_code_cell_for_the_student():
    cells = load_template().cells
    marks = [i for i, c in enumerate(cells) if c.source.startswith("## ")]
    ends = [*marks[1:], len(cells)]
    for start, end in zip(marks, ends, strict=True):
        last = cells[end - 1]
        assert last.cell_type == "code", cells[start].source
        assert last.source.strip() == "", cells[start].source


def test_the_shortlist_comes_from_the_slice_definitions(executed):
    """Generated at run time, so the template cannot drift from the code.

    The table is built by ``slices.shortlist()`` rather than here, because the
    stage 1 lesson shows the same one. Two notebooks assembling it by hand is
    how the two come apart.
    """
    code = "\n".join(c.source for c in executed.cells if c.cell_type == "code")
    assert "slices.shortlist()" in code
    for slice_id in slices.list_slices():
        assert f'"{slice_id}"' not in code, "the shortlist is hand-typed"
    shown = "".join(
        o.get("data", {}).get("text/plain", "")
        for c in executed.cells
        if c.cell_type == "code"
        for o in c.outputs
    )
    for slice_id in slices.list_slices():
        assert slice_id in shown


def test_the_shortlist_shows_which_slices_have_no_denominator(executed):
    """That difference is teaching material: a rate needs a denominator."""
    shown = "".join(
        o.get("data", {}).get("text/plain", "")
        for c in executed.cells
        if c.cell_type == "code"
        for o in c.outputs
    )
    for slice_id in slices.list_slices():
        row = next(line for line in shown.splitlines() if slice_id in line)
        denominator = slices.get(slice_id).denominator
        if denominator is None:
            assert row.split()[-2:] == ["none", "no"], row
        else:
            assert row.split()[-2:] == [denominator, "yes"], row


def test_the_template_is_not_a_lesson():
    """It is the student's file: no solution tags, no exercise tags, no checks."""
    nb = load_template()
    assert not any(tags(c) & {"solution", "exercise"} for c in nb.cells)
    assert "CWAI-SOLUTION" not in TEMPLATE.read_text()


def test_every_cell_has_a_deliberate_stable_id():
    """nbformat invents a random id for a cell without one, and a new one each save."""
    raw = nbformat.reads(TEMPLATE.read_text(), as_version=4)
    ids = [c["id"] for c in raw.cells]
    assert len(set(ids)) == len(ids)
    assert not [i for i in ids if re.fullmatch(r"[0-9a-f]{8}", i)], ids
    assert nbformat.reads(nbformat.writes(raw), as_version=4).cells == raw.cells
    assert [c["id"] for c in nbformat.reads(nbformat.writes(raw), 4).cells] == ids


def test_the_templates_prompts_pass_the_prose_gate():
    """Its prompts are the first English a student reads in their own file."""
    assert check_prose.check_notebook(TEMPLATE) == []


def test_the_template_is_not_copied_into_the_student_folder(tmp_path):
    out = tmp_path / "student"
    build(REPO / "notebooks", out)
    assert not list(out.rglob(TEMPLATE_NAME))


def test_the_exclusion_is_by_name_and_other_notebooks_are_still_copied(tmp_path):
    src = tmp_path / "notebooks" / "04-project"
    src.mkdir(parents=True)
    nbformat.write(nbformat.v4.new_notebook(), src / TEMPLATE_NAME)
    nbformat.write(nbformat.v4.new_notebook(), src / "lesson.ipynb")
    out = tmp_path / "student"
    build(tmp_path / "notebooks", out)
    assert [p.name for p in out.rglob("*.ipynb")] == ["lesson.ipynb"]
    assert stale_paths(tmp_path / "notebooks", out) == []


def section(heading_start):
    cells = load_template().cells
    start = next(i for i, c in enumerate(cells) if c.source.startswith(heading_start))
    return cells[start].source


def test_everyone_joins_the_traffic_counts_at_authority_level():
    """Design 7.6: no slice is left without a join, so no choice of table."""
    text = section("## 5.")
    assert "load_traffic_counts" in text
    assert "authority" in text
    assert "denominator column" in text
    assert "Pick a second table" not in text


def test_the_rates_section_sends_a_slice_without_a_denominator_away_first():
    text = section("## 6.")
    assert text.index("no denominator") < text.index("Compare")
    assert "road" not in text.lower().replace("roads", "")  # no "which road"
    assert "highest by count" in text and "highest by rate" in text


def test_the_limits_section_has_an_example_for_each_slice_with_no_denominator():
    """Two slices have no denominator, and each needs its own example.

    The defining columns are hard-coded: each lives inside a slice's select
    lambda. Whoever changes an example must change this test too.
    """
    lines = section("## 7.").splitlines()
    strong = [line for line in lines if "strong sentence" in line]
    assert len(strong) == 3, strong
    pedestrians = [line for line in strong if "for pedestrians" in line]
    after_dark = [line for line in strong if "for after dark" in line]
    assert len(pedestrians) == 1 and "`casualty_type`" in pedestrians[0]
    assert len(after_dark) == 1 and "`light_conditions`" in after_dark[0]
    assert "how many people walk" in pedestrians[0]
    assert "traffic after dark" in after_dark[0]


def test_a_stale_student_copy_of_the_template_is_reported_as_orphaned(tmp_path):
    src = tmp_path / "notebooks"
    (src / "04-project").mkdir(parents=True)
    nbformat.write(nbformat.v4.new_notebook(), src / "04-project" / TEMPLATE_NAME)
    out = tmp_path / "student"
    (out / "04-project").mkdir(parents=True)
    nbformat.write(nbformat.v4.new_notebook(), out / "04-project" / TEMPLATE_NAME)
    assert stale_paths(src, out) == [Path("04-project") / TEMPLATE_NAME]
