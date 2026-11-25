import json
from pathlib import Path

import jsonschema
import pandas as pd
import pytest
from make_synthetic import make_sensor_series, write_all

from cwai import registry
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


def test_committed_clean_data_matches_regenerated(tmp_path):
    """Drift guard: a numpy/pyarrow upgrade must not silently change the data
    that students' stored answers were computed from.

    Compares decoded frame contents exactly (not file bytes), so harmless
    Parquet metadata differences cannot cause false alarms while any change in
    a value, dtype or column does.
    """
    relpath = registry.get("sensor-clean").relpath
    write_all(tmp_path)
    committed = pd.read_parquet(registry.data_root() / relpath)
    regenerated = pd.read_parquet(tmp_path / relpath)
    pd.testing.assert_frame_equal(regenerated, committed, check_exact=True)
    pd.testing.assert_frame_equal(make_sensor_series(), committed, check_exact=True)
