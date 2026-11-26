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
    """Generated at run time, so the template cannot drift from the code."""
    code = "\n".join(c.source for c in executed.cells if c.cell_type == "code")
    assert "list_slices" in code
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
    assert TEMPLATE_NAME == "my-analysis-template.ipynb"


def test_the_exclusion_is_by_name_and_other_notebooks_are_still_copied(tmp_path):
    src = tmp_path / "notebooks" / "04-project"
    src.mkdir(parents=True)
    nbformat.write(nbformat.v4.new_notebook(), src / TEMPLATE_NAME)
    nbformat.write(nbformat.v4.new_notebook(), src / "lesson.ipynb")
    out = tmp_path / "student"
    build(tmp_path / "notebooks", out)
    assert [p.name for p in out.rglob("*.ipynb")] == ["lesson.ipynb"]
    assert stale_paths(tmp_path / "notebooks", out) == []
