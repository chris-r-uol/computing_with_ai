from pathlib import Path

import nbformat
import pytest
import yaml
from build_student_notebooks import (
    EXERCISE_TAG,
    HINT_TIERS,
    MissingHintError,
    check_notebook_hints,
    exercise_ids,
    hints_file_for,
    load_hints,
    validate_hints,
)

REPO = Path(__file__).resolve().parent.parent
GOOD = {"nudge": "look here", "method": "do this in prose"}


def exercise_cell(ex_id=None):
    meta = {"tags": [EXERCISE_TAG]}
    if ex_id is not None:
        meta["cwai"] = {"id": ex_id}
    return nbformat.v4.new_code_cell("# your code here", metadata=meta)


def notebook(*ex_ids):
    nb = nbformat.v4.new_notebook()
    nb.cells = [nbformat.v4.new_markdown_cell("prose")]
    nb.cells += [exercise_cell(i) for i in ex_ids]
    return nb


def lay_out(tmp_path, nb, hints):
    """Build a miniature repo: notebooks/<stage>/<name>.ipynb and hints/<stage>.yml."""
    path = tmp_path / "notebooks" / "01-foundations" / "01-a.ipynb"
    path.parent.mkdir(parents=True)
    nbformat.write(nb, path)
    if hints is not None:
        (tmp_path / "hints").mkdir()
        (tmp_path / "hints" / "01-foundations.yml").write_text(yaml.safe_dump(hints))
    return path


def test_every_exercise_has_nudge_and_method():
    # A gate for the future: today's notebooks have no exercises, so the cases
    # below are what actually exercise the pass and fail paths.
    for nb_path in REPO.glob("notebooks/**/*.ipynb"):
        check_notebook_hints(nb_path)


def test_missing_hint_names_the_exercise_and_tier():
    with pytest.raises(MissingHintError) as exc:
        validate_hints({"ex-1": {"nudge": "look here"}}, ["ex-1"])
    assert "ex-1" in str(exc.value) and "method" in str(exc.value)


def test_hint_tiers_are_restricted_to_known_names():
    with pytest.raises(MissingHintError) as exc:
        validate_hints({"ex-1": {"nudge": "a", "method": "b", "answer": "c"}}, ["ex-1"])
    assert "answer" in str(exc.value)


def test_complete_hints_pass_and_code_tier_is_optional():
    validate_hints({"ex-1": GOOD, "ex-2": {**GOOD, "code": "x = 1"}}, ["ex-1", "ex-2"])
    assert HINT_TIERS == ("nudge", "method", "code")


def test_exercise_with_no_hints_at_all_is_reported():
    with pytest.raises(MissingHintError) as exc:
        validate_hints({}, ["ex-9"])
    assert "ex-9" in str(exc.value)


def test_blank_hint_text_counts_as_missing():
    with pytest.raises(MissingHintError) as exc:
        validate_hints({"ex-1": {"nudge": "a", "method": "   "}}, ["ex-1"])
    assert "method" in str(exc.value)


def test_hints_for_other_notebooks_in_the_stage_are_ignored():
    validate_hints({"ex-1": GOOD, "elsewhere": {"nudge": "x"}}, ["ex-1"])


def test_exercise_ids_come_from_metadata_in_order():
    assert exercise_ids(notebook("b", "a")) == ["b", "a"]


def test_exercise_ids_ignores_non_exercise_cells():
    nb = notebook("a")
    nb.cells.append(nbformat.v4.new_code_cell("x = 1", metadata={"cwai": {"id": "z"}}))
    assert exercise_ids(nb) == ["a"]


def test_exercise_without_id_is_an_error():
    with pytest.raises(ValueError, match="id"):
        exercise_ids(notebook(None))


def test_duplicate_exercise_ids_are_an_error():
    with pytest.raises(ValueError, match="dup"):
        exercise_ids(notebook("dup", "dup"))


def test_hints_file_for_maps_stage_directory():
    nb = Path("/r/notebooks/01-foundations/03-loops.ipynb")
    assert hints_file_for(nb) == Path("/r/hints/01-foundations.yml")


def test_load_hints_reads_yaml(tmp_path):
    f = tmp_path / "h.yml"
    f.write_text("ex-1:\n  nudge: look\n  method: think\n")
    assert load_hints(f) == {"ex-1": {"nudge": "look", "method": "think"}}


def test_load_hints_of_empty_file_is_empty(tmp_path):
    f = tmp_path / "h.yml"
    f.write_text("# nothing yet\n")
    assert load_hints(f) == {}


def test_load_hints_rejects_wrong_shape(tmp_path):
    f = tmp_path / "h.yml"
    f.write_text("- not\n- a mapping\n")
    with pytest.raises(ValueError):
        load_hints(f)


def test_notebook_with_complete_hints_passes(tmp_path):
    check_notebook_hints(lay_out(tmp_path, notebook("ex-1"), {"ex-1": GOOD}))


def test_notebook_with_incomplete_hints_fails(tmp_path):
    path = lay_out(tmp_path, notebook("ex-1"), {"ex-1": {"nudge": "x"}})
    with pytest.raises(MissingHintError, match="method"):
        check_notebook_hints(path)


def test_notebook_with_exercises_but_no_hints_file_fails(tmp_path):
    path = lay_out(tmp_path, notebook("ex-1"), None)
    with pytest.raises(MissingHintError, match="ex-1"):
        check_notebook_hints(path)


def test_notebook_without_exercises_needs_no_hints_file(tmp_path):
    check_notebook_hints(lay_out(tmp_path, notebook(), None))
