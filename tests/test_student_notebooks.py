import json

import nbformat
import pytest
from build_student_notebooks import (
    EXERCISE_TAG,
    SOLUTION_MARKER,
    SOLUTION_TAG,
    STUB_MARKER,
    TEXT_STUB,
    SolutionMarkerError,
    build,
    main,
    strip_solutions,
    wrap_solution,
)

SECRET = "answer = 42"


def nb_with_solution():
    nb = nbformat.v4.new_notebook()
    exercise = nbformat.v4.new_code_cell(
        "# set answer", metadata={"tags": [EXERCISE_TAG]}
    )
    solution = nbformat.v4.new_code_cell(
        wrap_solution(SECRET), metadata={"tags": [SOLUTION_TAG]}
    )
    solution.outputs = [nbformat.v4.new_output("stream", text=SECRET)]
    solution.execution_count = 3
    nb.cells = [nbformat.v4.new_markdown_cell("Intro"), solution, exercise]
    return nb


def write(nb, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, path)


def test_solution_cells_are_replaced_with_stub():
    out = strip_solutions(nb_with_solution())
    assert out.cells[1].source.strip() == STUB_MARKER


def test_tags_are_preserved_so_rebuilds_are_idempotent():
    once = strip_solutions(nb_with_solution())
    assert SOLUTION_TAG in once.cells[1].metadata.tags
    assert strip_solutions(once).cells[1].source.strip() == STUB_MARKER


def test_non_solution_cells_are_untouched():
    nb = nb_with_solution()
    assert strip_solutions(nb).cells[0].source == nb.cells[0].source
    assert strip_solutions(nb).cells[2].source == nb.cells[2].source


def test_solution_content_and_marker_do_not_survive_anywhere():
    # Outputs and the CWAI-SOLUTION marker must go too, or the answer leaks.
    out = nbformat.writes(strip_solutions(nb_with_solution()))
    assert SECRET not in out
    assert SOLUTION_MARKER not in out


def test_strip_does_not_mutate_its_input():
    nb = nb_with_solution()
    strip_solutions(nb)
    assert SECRET in nb.cells[1].source


def test_wrapped_solution_carries_the_marker_the_site_test_greps_for():
    assert SOLUTION_MARKER == "CWAI-SOLUTION"
    assert SOLUTION_MARKER in wrap_solution(SECRET)
    assert SECRET in wrap_solution(SECRET)


def test_build_mirrors_tree_and_hides_solutions(tmp_path):
    src, out = tmp_path / "notebooks", tmp_path / "student"
    write(nb_with_solution(), src / "01-foundations" / "01-a.ipynb")
    written = build(src, out)
    assert written == [out / "01-foundations" / "01-a.ipynb"]
    assert SECRET not in written[0].read_text()


def test_building_twice_gives_identical_bytes(tmp_path):
    src, out = tmp_path / "notebooks", tmp_path / "student"
    write(nb_with_solution(), src / "s" / "a.ipynb")
    first = build(src, out)[0].read_bytes()
    assert build(src, out)[0].read_bytes() == first


def test_building_student_output_again_is_a_fixed_point(tmp_path):
    src, out, out2 = (tmp_path / n for n in ("notebooks", "student", "again"))
    write(nb_with_solution(), src / "s" / "a.ipynb")
    build(src, out)
    build(out, out2)
    assert (out2 / "s" / "a.ipynb").read_bytes() == (out / "s" / "a.ipynb").read_bytes()


def test_check_passes_when_up_to_date_and_fails_when_stale(tmp_path, capsys):
    src, out = tmp_path / "notebooks", tmp_path / "student"
    write(nb_with_solution(), src / "s" / "a.ipynb")
    args = ["--src", str(src), "--out", str(out), "--check"]
    assert main(args) == 1  # nothing built yet
    build(src, out)
    assert main(args) == 0
    stale = out / "s" / "a.ipynb"
    data = json.loads(stale.read_text())
    data["cells"][0]["source"] = "edited by hand"
    stale.write_text(json.dumps(data))
    assert main(args) == 1
    assert "a.ipynb" in capsys.readouterr().out


def test_check_fails_on_orphaned_student_notebook(tmp_path):
    src, out = tmp_path / "notebooks", tmp_path / "student"
    write(nb_with_solution(), src / "s" / "a.ipynb")
    build(src, out)
    write(nb_with_solution(), out / "s" / "gone.ipynb")
    assert main(["--src", str(src), "--out", str(out), "--check"]) == 1


def test_check_does_not_write_anything(tmp_path):
    src, out = tmp_path / "notebooks", tmp_path / "student"
    write(nb_with_solution(), src / "s" / "a.ipynb")
    main(["--src", str(src), "--out", str(out), "--check"])
    assert not out.exists()


def test_main_without_check_builds(tmp_path):
    src, out = tmp_path / "notebooks", tmp_path / "student"
    write(nb_with_solution(), src / "s" / "a.ipynb")
    assert main(["--src", str(src), "--out", str(out)]) == 0
    assert (out / "s" / "a.ipynb").exists()


def test_checkpoint_directories_are_ignored(tmp_path):
    src, out = tmp_path / "notebooks", tmp_path / "student"
    write(nb_with_solution(), src / "s" / ".ipynb_checkpoints" / "a-checkpoint.ipynb")
    assert build(src, out) == []


@pytest.mark.parametrize("tags", [[], ["other"]])
def test_untagged_cells_are_never_stubbed(tags):
    nb = nbformat.v4.new_notebook()
    nb.cells = [nbformat.v4.new_code_cell("x = 1", metadata={"tags": tags})]
    assert strip_solutions(nb).cells[0].source == "x = 1"


def test_committed_student_notebooks_are_up_to_date():
    assert main(["--check"]) == 0


@pytest.mark.parametrize("tags", [[], ["Solution"], ["solutions"]])
def test_marker_in_a_cell_without_the_solution_tag_fails_fast(tags):
    nb = nbformat.v4.new_notebook()
    nb.cells = [
        nbformat.v4.new_code_cell(wrap_solution(SECRET), metadata={"tags": tags})
    ]
    with pytest.raises(SolutionMarkerError, match="solution"):
        strip_solutions(nb)


def test_build_and_check_report_a_mistagged_solution(tmp_path):
    src, out = tmp_path / "notebooks", tmp_path / "student"
    nb = nbformat.v4.new_notebook()
    nb.cells = [nbformat.v4.new_code_cell(wrap_solution(SECRET))]
    write(nb, src / "s" / "a.ipynb")
    assert main(["--src", str(src), "--out", str(out)]) == 2
    assert main(["--src", str(src), "--out", str(out), "--check"]) == 2
    assert not out.exists()


def markdown_solution():
    cell = nbformat.v4.new_markdown_cell(
        wrap_solution("The answer is 42 ![](attachment:img.png)"),
        metadata={"tags": [SOLUTION_TAG], "cwai": {"note": "secret"}},
    )
    cell["attachments"] = {"img.png": {"image/png": "SECRETBYTES"}}
    nb = nbformat.v4.new_notebook()
    nb.cells = [cell]
    return nb


def test_markdown_solution_gets_a_note_not_a_heading():
    cell = strip_solutions(markdown_solution()).cells[0]
    assert cell.source == TEXT_STUB
    assert not cell.source.startswith("#")


def test_markdown_solution_loses_attachments_and_extra_metadata():
    out = nbformat.writes(strip_solutions(markdown_solution()))
    assert "SECRETBYTES" not in out
    assert "attachments" not in out
    assert "secret" not in out
    assert SOLUTION_TAG in out


def test_stripped_markdown_solution_is_a_fixed_point():
    once = strip_solutions(markdown_solution())
    assert strip_solutions(once) == once


@pytest.mark.parametrize("flags", [[], ["--check"]])
def test_missing_source_directory_is_an_error_not_a_pass(tmp_path, flags, capsys):
    args = ["--src", str(tmp_path / "typo"), "--out", str(tmp_path / "o"), *flags]
    assert main(args) != 0
    assert "typo" in capsys.readouterr().err
