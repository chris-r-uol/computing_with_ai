"""The eight canonical slices and the metrics recomputed from them."""

import pytest

from cwai import data, slices


def test_there_are_eight_slices_with_unique_ids():
    assert len(slices.SLICES) == 8
    assert len({s.id for s in slices.SLICES}) == 8


@pytest.mark.parametrize(
    "slice_id,rows",
    [
        ("cyclists", 2304),
        ("pedestrians", 5016),
        ("leeds", 7298),
        ("bradford", 5163),
        ("kirklees", 3327),
        ("wakefield", 2889),
        ("calderdale", 1808),
        ("after-dark", 6328),
    ],
)
def test_each_slice_selects_the_expected_number_of_rows(slice_id, rows):
    assert len(slices.load(slice_id)) == rows


def test_two_slices_have_no_denominator_column():
    without = {s.id for s in slices.SLICES if s.denominator is None}
    assert without == {"pedestrians", "after-dark"}


def test_every_denominator_is_a_real_traffic_count_column():
    columns = set(data.load_traffic_counts().columns)
    for s in slices.SLICES:
        if s.denominator is not None:
            assert s.denominator in columns


def test_unknown_slice_id_names_near_matches():
    with pytest.raises(slices.UnknownSliceError) as exc:
        slices.get("cyclist")
    assert "cyclists" in str(exc.value)


def test_unknown_slice_id_with_no_near_match_lists_the_choices():
    with pytest.raises(slices.UnknownSliceError) as exc:
        slices.get("zzz")
    assert "cyclists" in str(exc.value) and "after-dark" in str(exc.value)


def test_asking_for_a_rate_on_a_slice_with_no_denominator_says_which():
    with pytest.raises(slices.NoDenominatorError) as exc:
        slices.denominator_column("after-dark")
    assert "after-dark" in str(exc.value)
    assert "no denominator" in str(exc.value).lower()


def test_denominator_column_returns_the_name_when_there_is_one():
    assert slices.denominator_column("cyclists") == "pedal_cycles"


def test_row_count_metric_recomputes_per_slice():
    m = slices.METRICS["slice-row-count"]
    assert m.compute(slices.get("cyclists")) == 2304
    assert m.compute(slices.get("after-dark")) == 6328


def test_ksi_percent_metric_recomputes_per_slice():
    m = slices.METRICS["slice-ksi-percent"]
    assert m.compute(slices.get("cyclists")) == pytest.approx(30.9462, abs=0.001)
    assert m.compute(slices.get("after-dark")) == pytest.approx(31.7478, abs=0.001)


def test_ksi_percent_metric_declares_a_tolerance_and_number_kind():
    m = slices.METRICS["slice-ksi-percent"]
    assert m.kind == "number" and m.tolerance > 0


def test_row_count_metric_is_exact():
    assert slices.METRICS["slice-row-count"].tolerance == 0
