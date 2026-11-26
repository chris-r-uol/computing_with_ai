from pathlib import Path

import nbformat
import pandas as pd
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
from render_site import render

from cwai import hints

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
    paths = [
        p
        for p in REPO.glob("notebooks/**/*.ipynb")
        if ".ipynb_checkpoints" not in p.parts
    ]
    # Without this, renaming notebooks/ makes the constraint silently vacuous.
    assert paths, "found no notebooks under notebooks/"
    for nb_path in paths:
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


@pytest.mark.parametrize("nudge", [None, "", "  "])
def test_nudge_is_required_even_when_method_is_present(nudge):
    tiers = {"method": "approach"} if nudge is None else {"nudge": nudge, "method": "m"}
    with pytest.raises(MissingHintError) as exc:
        validate_hints({"ex-1": tiers}, ["ex-1"])
    assert "nudge" in str(exc.value) and "method" not in str(exc.value)


def write_hints(tmp_path, data, name="hints.yml"):
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data))
    return path


def test_hint_renders_one_disclosure_per_tier_plus_a_wrapper(tmp_path):
    path = write_hints(tmp_path, {"demo": {"nudge": "look here", "method": "do this"}})
    html = hints.hint("demo", path=path).data
    assert html.count("<details") == 3  # wrapper + two tiers
    assert "Nudge" in html and "Method" in html
    assert "look here" in html and "do this" in html


def test_hint_orders_tiers_and_labels_them_from_tier_labels(tmp_path):
    path = write_hints(
        tmp_path,
        {"demo": {"code": "df.head()", "nudge": "n", "method": "m"}},
    )
    html = hints.hint("demo", path=path).data
    assert html.index("Nudge") < html.index("Method") < html.index("Show the answer")


def test_hint_escapes_html_in_the_hint_text(tmp_path):
    path = write_hints(tmp_path, {"demo": {"nudge": "use <b> & co", "method": "m"}})
    html = hints.hint("demo", path=path).data
    assert "use &lt;b&gt; &amp; co" in html


def test_hint_on_an_unknown_exercise_names_near_matches(tmp_path):
    path = write_hints(tmp_path, {"first-look-severity": {"nudge": "n", "method": "m"}})
    with pytest.raises(hints.UnknownExerciseError) as exc:
        hints.hint("first-look-severty", path=path)
    assert "first-look-severity" in str(exc.value)


def test_hint_renders_no_open_attribute_so_every_tier_starts_collapsed(tmp_path):
    path = write_hints(tmp_path, {"demo": {"nudge": "n", "method": "m", "code": "c"}})
    assert "open" not in hints.hint("demo", path=path).data


def test_hint_renders_the_answer_tier_in_pre(tmp_path):
    path = write_hints(
        tmp_path, {"demo": {"nudge": "n", "method": "m", "answer": "a < b"}}
    )
    html = hints.hint("demo", path=path).data
    assert "A model answer" in html
    assert "<pre>a &lt; b</pre>" in html


def test_hint_renders_the_code_tier_in_pre_code(tmp_path):
    path = write_hints(tmp_path, {"demo": {"nudge": "n", "method": "m", "code": "x"}})
    assert "<pre><code>x</code></pre>" in hints.hint("demo", path=path).data


def test_tier_constants_have_the_agreed_shape():
    assert hints.HINT_TIERS == ("nudge", "method", "code", "answer")
    assert set(hints.TIER_LABELS) == set(hints.HINT_TIERS)
    assert hints.REQUIRED_TIERS == ("nudge", "method")
    assert hints.EXCLUSIVE_TIERS == frozenset({"code", "answer"})


def test_hint_without_a_path_reads_every_yml_under_hints(tmp_path, monkeypatch):
    (tmp_path / "hints").mkdir()
    write_hints(tmp_path / "hints", {"a": {"nudge": "na", "method": "ma"}}, "one.yml")
    write_hints(tmp_path / "hints", {"b": {"nudge": "nb", "method": "mb"}}, "two.yml")
    monkeypatch.setattr(hints.registry, "repo_root", lambda: tmp_path)
    assert "na" in hints.hint("a").data
    assert "nb" in hints.hint("b").data


def test_hint_without_a_path_rejects_an_id_in_two_files(tmp_path, monkeypatch):
    (tmp_path / "hints").mkdir()
    entry = {"dup": {"nudge": "n", "method": "m"}}
    write_hints(tmp_path / "hints", entry, "one.yml")
    write_hints(tmp_path / "hints", entry, "two.yml")
    monkeypatch.setattr(hints.registry, "repo_root", lambda: tmp_path)
    with pytest.raises(ValueError) as exc:
        hints.hint("dup")
    assert "one.yml" in str(exc.value) and "two.yml" in str(exc.value)


def test_reveal_wraps_a_dataframes_html_in_a_collapsed_disclosure():
    html = hints.reveal(pd.DataFrame({"a": [1, 2]})).data
    assert html.startswith("<details") and "open" not in html
    assert "<table" in html
    assert "Show the output" in html


def test_reveal_takes_a_custom_label():
    assert "What did it print?" in hints.reveal(42, label="What did it print?").data


@pytest.mark.parametrize("value", [42, "text", None, 3.5, ["a", "b"]])
def test_reveal_renders_plain_values_without_an_html_representation(value):
    html = hints.reveal(value).data
    assert "<details" in html and repr(value).replace("'", "&#x27;") in html


def test_reveal_falls_back_to_repr_when_repr_html_raises():
    class Hostile:
        def _repr_html_(self):
            raise RuntimeError("no")

        def __repr__(self):
            return "Hostile()"

    assert "Hostile()" in hints.reveal(Hostile()).data


def test_reveal_escapes_a_plain_value_that_looks_like_markup():
    assert "&lt;script&gt;" in hints.reveal("<script>").data


@pytest.mark.slow
def test_rendered_hint_survives_a_quarto_render(tmp_path):
    """All four disclosures and every tier's text reach the published HTML."""
    from test_site import _copy_site

    tiers = {
        "nudge": "NUDGETEXT1",
        "method": "METHODTEXT2",
        "code": "CODETEXT3",
        "answer": "ANSWERTEXT4",
    }
    hint_file = write_hints(tmp_path, {"survive": tiers})
    nb = nbformat.v4.new_notebook()
    nb.cells = [
        nbformat.v4.new_markdown_cell("# Hint page"),
        nbformat.v4.new_code_cell(
            f"from cwai.hints import hint\nhint('survive', path={str(hint_file)!r})"
        ),
    ]
    nb.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    path = tmp_path / "hint-page.ipynb"
    nbformat.write(nb, path)
    out = tmp_path / "out"
    done = render(_copy_site(tmp_path / "site"), out, notebooks=[path])
    assert done.returncode == 0, done.stdout + done.stderr
    (page,) = out.rglob("hint-page.html")
    html = page.read_text()
    # The source cell is also in the page; the tier text only exists if it ran.
    assert "survive" in html
    assert html.count("<details") >= 4
    for tier, text in tiers.items():
        assert hints.TIER_LABELS[tier] in html
        assert text in html
    assert "<details open" not in html
