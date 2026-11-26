import json
from pathlib import Path

import jsonschema
import numpy as np
import pandas as pd
import pytest
from make_synthetic import make_sensor_series, write_all

from cwai import checks as checks_module
from cwai import registry, slices
from cwai.checks import (
    TOLERANCE,
    CheckFailed,
    UnknownCheckError,
    check,
    expect_columns,
    expect_shape,
    load_expected,
)

SCHEMA = Path(__file__).parent.parent / "checks" / "expected.schema.json"


def test_passing_numeric_check_is_truthy():
    assert check("demo-number", 42)


def test_failing_numeric_check_reports_both_values():
    result = check("demo-number", 41)
    assert not result.passed
    assert "41" in result.message and "42" in result.message


def test_numeric_check_respects_tolerance():
    assert check("demo-float", 0.1 + 0.2)


def test_numeric_check_outside_tolerance_fails():
    assert not check("demo-float", 0.3 + 10 * TOLERANCE)


def test_non_numeric_value_fails_politely_instead_of_raising():
    result = check("demo-number", "forty-two")
    assert not result and "number" in result.message


def test_repr_reads_as_feedback():
    assert repr(check("demo-number", 42)).startswith("✓")
    failing = repr(check("demo-number", 41))
    assert failing.startswith("✗") and "42" in failing and "41" in failing


def test_unknown_check_name_lists_nearby_names():
    with pytest.raises(UnknownCheckError) as exc:
        check("demo-numbr", 42)
    assert "demo-number" in str(exc.value)


def test_unknown_check_name_with_no_near_match_says_what_to_do():
    with pytest.raises(UnknownCheckError) as exc:
        check("zzzzzz", 1)
    assert "zzzzzz" in str(exc.value) and "spelling" in str(exc.value)


def test_expect_columns_names_the_missing_column():
    with pytest.raises(CheckFailed) as exc:
        expect_columns(pd.DataFrame({"a": [1]}), ["a", "b"])
    assert "b" in str(exc.value) and "a" in str(exc.value)


def test_expect_columns_passes_silently():
    assert expect_columns(pd.DataFrame({"a": [1], "b": [2]}), ["a", "b"]) is None


def test_expect_shape_reports_expected_and_found():
    with pytest.raises(CheckFailed) as exc:
        expect_shape(pd.DataFrame({"a": [1, 2]}), rows=3)
    assert "3 rows" in str(exc.value) and "2 rows" in str(exc.value)


def test_expect_shape_ignores_unspecified_dimension():
    expect_shape(pd.DataFrame({"a": [1, 2]}), rows=2)
    expect_shape(pd.DataFrame({"a": [1, 2]}), cols=1)


def test_expect_shape_with_nothing_to_check_is_an_error():
    # It used to pass silently, so a student got a tick for nothing.
    with pytest.raises(ValueError, match="rows"):
        expect_shape(pd.DataFrame({"a": [1, 2]}))


def test_expected_json_validates_against_schema():
    jsonschema.validate(load_expected(), json.loads(SCHEMA.read_text()))


def test_every_expected_entry_has_a_supported_type():
    # a shape the JS consumer cannot read must fail CI
    for entry in load_expected().values():
        assert entry["type"] in {"number", "string", "list", "shape"}


def test_schema_rejects_unsupported_type():
    bad = {"x": {"type": "matrix", "value": 1}}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, json.loads(SCHEMA.read_text()))


def test_schema_allows_tolerance_on_a_number():
    jsonschema.validate(
        {"x": {"type": "number", "value": 1.0, "tolerance": 0.01}},
        json.loads(SCHEMA.read_text()),
    )


@pytest.mark.parametrize(
    ("kind", "value"),
    [("list", [1, 2]), ("string", "Leeds"), ("shape", [3, 2])],
)
def test_schema_rejects_tolerance_on_anything_but_a_number(kind, value):
    """The comparator honours tolerance for numbers only.

    Permitting it elsewhere would invite the site's JavaScript author to
    implement a tolerance the Python side ignores, and a student would see the
    notebook say "wrong" and the site say "right".
    """
    bad = {"x": {"type": kind, "value": value, "tolerance": 0.5}}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, json.loads(SCHEMA.read_text()))


@pytest.mark.parametrize(
    "answer", [[1, 2, 3], (1, 2, 3), np.array([1, 2, 3]), pd.Series([1, 2, 3])]
)
def test_a_list_entry_accepts_any_sequence(typed_checks, answer):
    """Documented in checks/README.md: the JavaScript must accept these too."""
    assert check("fx-list", answer)


@pytest.mark.parametrize(
    "answer", [pd.DataFrame({"a": [1, 2, 3], "b": [1, 2, 3]}), [3, 2], (3, 2)]
)
def test_a_shape_entry_accepts_a_shaped_result_or_a_bare_pair(typed_checks, answer):
    assert check("fx-shape", answer)


def test_checks_readme_states_the_comparison_contract():
    """The JavaScript author reads this file, so it must not go missing."""
    text = (SCHEMA.parent / "README.md").read_text(encoding="utf-8")
    for required in (
        "tolerance",
        "order-sensitive",
        "two-element array",
        "including case",
        # _compare normalises sequences and reads .shape when there is one;
        # a JS author following a README that omitted either would disagree
        # with the notebook on an answer the notebook accepts.
        "accepts any sequence",
        "carrying its own shape",
    ):
        assert required in text, required


@pytest.mark.parametrize("key", ["sensor-clean", "sensor-faulty"])
def test_committed_synthetic_data_matches_regenerated(tmp_path, key):
    """Drift guard: a numpy/pyarrow upgrade must not silently change the data
    that students' stored answers were computed from.

    Both files, not just the clean one: ``sensor-faulty`` is the artefact whose
    planted faults the lessons depend on, so a generator whose random stream
    moved would move the faults the exercises point at.

    Compares decoded frame contents exactly (not file bytes), so harmless
    Parquet metadata differences cannot cause false alarms while any change in
    a value, dtype or column does.
    """
    relpath = registry.get(key).relpath
    write_all(tmp_path)
    committed = pd.read_parquet(registry.data_root() / relpath)
    regenerated = pd.read_parquet(tmp_path / relpath)
    pd.testing.assert_frame_equal(regenerated, committed, check_exact=True)


def test_committed_clean_data_matches_the_generator_called_directly(tmp_path):
    committed = pd.read_parquet(
        registry.data_root() / registry.get("sensor-clean").relpath
    )
    pd.testing.assert_frame_equal(make_sensor_series(), committed, check_exact=True)


FIXTURE = Path(__file__).parent / "fixtures_expected.json"


@pytest.fixture
def typed_checks(monkeypatch):
    """Point check() at a fixture holding one entry per answer type."""
    monkeypatch.setattr(checks_module, "_EXPECTED_PATH", FIXTURE)
    assert set(load_expected(FIXTURE)) == {"fx-string", "fx-list", "fx-shape"}


def test_fixture_validates_against_schema():
    jsonschema.validate(load_expected(FIXTURE), json.loads(SCHEMA.read_text()))


def test_string_check_passes_on_exact_match(typed_checks):
    assert check("fx-string", "Leeds")


def test_string_check_failure_names_expected_and_found(typed_checks):
    result = check("fx-string", "leeds")
    assert not result
    assert "'Leeds'" in result.message and "'leeds'" in result.message
    assert "Expected the text" in result.message
    assert "capital letters" in result.message and "item by item" not in result.message


def test_list_check_passes_for_list_tuple_and_numpy(typed_checks):
    assert check("fx-list", [1, 2, 3])
    assert check("fx-list", (1, 2, 3))
    assert check("fx-list", np.array([1, 2, 3]))


def test_list_check_failure_names_expected_and_found(typed_checks):
    result = check("fx-list", [1, 2, 4])
    assert not result
    assert "[1, 2, 3]" in result.message and "[1, 2, 4]" in result.message
    assert "Expected the list" in result.message


def test_list_check_is_order_sensitive(typed_checks):
    assert not check("fx-list", [3, 2, 1])


def test_shape_check_passes_for_dataframe_and_tuple(typed_checks):
    assert check("fx-shape", pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]}))
    assert check("fx-shape", (3, 2))


def test_shape_check_failure_names_expected_and_found(typed_checks):
    result = check("fx-shape", pd.DataFrame({"a": [1, 2]}))
    assert not result
    assert "(3, 2)" in result.message and "(2, 1)" in result.message
    assert "Expected a shape" in result.message


@pytest.mark.parametrize(
    "entry",
    [
        {"type": "number", "value": "abc"},
        {"type": "string", "value": 5},
        {"type": "list", "value": "not a list"},
        {"type": "shape", "value": [3]},
        {"type": "shape", "value": [3, "x"]},
        {"type": "shape", "value": [3, 2, 1]},
    ],
)
def test_schema_rejects_value_that_does_not_match_type(entry):
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"x": entry}, json.loads(SCHEMA.read_text()))


def test_passing_a_big_table_does_not_dump_it_into_the_message():
    big = pd.DataFrame({"a": range(5000)})
    message = check("demo-number", big).message
    assert "DataFrame" in message and len(message) < 200


def test_long_wrong_list_is_truncated_in_the_message(typed_checks):
    message = check("fx-list", list(range(5000))).message
    assert "..." in message and len(message) < 250


def test_long_wrong_shape_is_truncated_in_the_message(typed_checks):
    message = check("fx-shape", list(range(5000))).message
    assert "..." in message and len(message) < 250


def test_number_check_shows_a_string_the_student_typed():
    message = check("demo-number", "42").message
    assert "'42'" in message and "not a number" in message


# --- the unattempted state ---------------------------------------------------


def test_an_untouched_stub_reads_as_unattempted_not_failed():
    result = checks_module.check("demo-number", checks_module.UNATTEMPTED)
    assert result.attempted is False
    assert result.passed is False
    assert "✗" not in repr(result)
    assert "failed" not in repr(result).lower()
    assert "not attempted yet" in repr(result)


def test_a_wrong_answer_still_reads_as_wrong():
    result = check("demo-number", 999)
    assert result.attempted is True and result.passed is False
    assert "✗" in repr(result)


def test_a_right_answer_still_reads_as_right():
    result = check("demo-number", 42)
    assert result.attempted is True and result.passed is True
    assert "✓" in repr(result)


def test_an_unattempted_result_is_still_falsey():
    assert not check("demo-number", checks_module.UNATTEMPTED)


def test_the_three_states_differ_without_colour():
    marks = {
        repr(check("demo-number", 42))[0],
        repr(check("demo-number", 999))[0],
        repr(check("demo-number", checks_module.UNATTEMPTED))[0],
    }
    assert len(marks) == 3


def test_an_unknown_check_name_still_raises_even_when_unattempted():
    """A typo in the check name is an authoring bug, not an unanswered exercise."""
    with pytest.raises(UnknownCheckError):
        check("no-such-check", checks_module.UNATTEMPTED)


def test_expect_columns_treats_the_sentinel_as_unattempted():
    expect_columns(checks_module.UNATTEMPTED, ["a", "b"])  # must not raise


def test_expect_shape_treats_the_sentinel_as_unattempted():
    expect_shape(checks_module.UNATTEMPTED, rows=3)  # must not raise


def test_expect_shape_still_rejects_nothing_to_check_when_unattempted():
    """The authoring bug is still a bug; only the student's blank is excused."""
    with pytest.raises(ValueError):
        expect_shape(checks_module.UNATTEMPTED)


# --- check_slice -------------------------------------------------------------


def test_check_slice_passes_the_right_answer_for_that_slice():
    assert checks_module.check_slice("slice-row-count", 2304, "cyclists").passed


def test_check_slice_rejects_another_slices_right_answer():
    result = checks_module.check_slice("slice-row-count", 6328, "cyclists")
    assert not result.passed
    assert "2304" in result.message


def test_check_slice_applies_the_metrics_tolerance():
    assert checks_module.check_slice("slice-ksi-percent", 30.946, "cyclists").passed
    assert not checks_module.check_slice("slice-ksi-percent", 31.5, "cyclists").passed


def test_check_slice_reads_an_untouched_stub_as_unattempted():
    result = checks_module.check_slice(
        "slice-row-count", checks_module.UNATTEMPTED, "cyclists"
    )
    assert result.attempted is False and "not attempted yet" in repr(result)


def test_check_slice_reads_an_unpicked_slice_as_unattempted():
    """A handoff cell has two stubs, and an unpicked slice is one of them.

    The lesson's cell is ``my_slice = ...  # your slice id here``, so that no
    student's slice is the authored default. A student who has not chosen yet
    has not attempted the exercise, and must be told that rather than handed a
    slice error for a slice they never named.
    """
    result = checks_module.check_slice("slice-row-count", 1, checks_module.UNATTEMPTED)
    assert result.attempted is False and "not attempted yet" in repr(result)


def test_the_two_unattempted_paths_say_different_things():
    """An unpicked slice and an unanswered question are not the same problem.

    Both are ``○``, and both must stay ``○``. But a student who has written
    their answer and not yet chosen a slice must not be told to replace the
    ``...`` with their answer, because they already did, and they are reading
    that message at the moment they are stuck. So the two messages must not
    collapse back into one.
    """
    no_slice = checks_module.check_slice(
        "slice-row-count", 1, checks_module.UNATTEMPTED
    )
    no_answer = checks_module.check_slice(
        "slice-row-count", checks_module.UNATTEMPTED, "cyclists"
    )
    assert no_slice.attempted is False and no_answer.attempted is False
    assert "not attempted yet" in no_slice.message
    assert "not attempted yet" in no_answer.message
    assert no_slice.message != no_answer.message
    # The defect this guards: the wrong instruction, to someone who followed it.
    assert "with your answer" not in no_slice.message
    assert "slice" in no_slice.message


def test_an_unpicked_slice_is_reported_before_an_unanswered_question():
    """Both stubs untouched is the published state, and the slice comes first.

    A student fills the slice cell before the answer cell, so that is the one
    to name when neither has been touched.
    """
    neither = checks_module.check_slice(
        "slice-row-count", checks_module.UNATTEMPTED, checks_module.UNATTEMPTED
    )
    assert "slice" in neither.message


def test_check_slice_still_raises_on_a_mistyped_slice_id():
    """Only the stub sentinel is unattempted. A typo stays an error.

    The counterpart of the test above: if an unpicked slice were read as
    unattempted by anything looser than an identity test, a real typo would be
    silently excused instead of explained.
    """
    with pytest.raises(slices.UnknownSliceError):
        checks_module.check_slice("slice-row-count", 1, "leedz")


def test_check_slice_on_an_unknown_slice_raises_the_slice_error():
    with pytest.raises(slices.UnknownSliceError):
        checks_module.check_slice("slice-row-count", 1, "cyclist")


def test_check_slice_on_an_unknown_metric_names_near_matches():
    with pytest.raises(UnknownCheckError) as exc:
        checks_module.check_slice("slice-row-counts", 1, "cyclists")
    assert "slice-row-count" in str(exc.value)


def test_check_slice_unknown_metric_raises_even_when_unattempted():
    with pytest.raises(UnknownCheckError):
        checks_module.check_slice(
            "slice-row-counts", checks_module.UNATTEMPTED, "cyclists"
        )


def test_check_slice_unknown_metric_raises_even_when_the_slice_is_unpicked():
    """A wrong name is a mistake in the course material, so it never waits."""
    with pytest.raises(UnknownCheckError):
        checks_module.check_slice("slice-row-counts", 1, checks_module.UNATTEMPTED)


def test_check_slice_gives_the_same_verdict_as_check_on_the_same_value():
    """Both go through _compare, so the wording is identical."""
    result = checks_module.check_slice("slice-row-count", "2304", "cyclists")
    assert "not a number" in result.message
