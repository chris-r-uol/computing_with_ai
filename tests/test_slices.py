"""The eight canonical slices and the metrics recomputed from them."""

import pandas as pd
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


def test_the_shortlist_is_one_row_per_slice_in_definition_order():
    """The lesson and the template both show this, so it lives here, once.

    Two notebooks building the same table by hand is how the two drift apart.
    """
    table = slices.shortlist()
    assert list(table.columns) == ["id", "label", "table", "denominator", "rate"]
    assert list(table["id"]) == slices.list_slices()
    assert list(table["label"]) == [s.label for s in slices.SLICES]


def test_the_shortlist_says_which_table_each_slice_cuts():
    """Without this column a student cannot say whether they counted people."""
    table = slices.shortlist().set_index("id")
    assert table.loc["cyclists", "table"] == "casualties"
    assert table.loc["pedestrians", "table"] == "casualties"
    assert set(table.loc[table["table"] == "casualties"].index) == {
        "cyclists",
        "pedestrians",
    }


def test_the_shortlist_spells_out_a_missing_denominator_rather_than_leaving_it_blank():
    table = slices.shortlist().set_index("id")
    assert (
        table.loc["after-dark", "denominator"],
        table.loc["after-dark", "rate"],
    ) == (
        "none",
        "no",
    )
    assert (table.loc["cyclists", "denominator"], table.loc["cyclists", "rate"]) == (
        "pedal_cycles",
        "yes",
    )


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


def test_a_slice_whose_table_name_is_misspelt_is_rejected_not_quietly_loaded(
    monkeypatch,
):
    """``load`` took anything that was not ``"collisions"`` to be the casualties.

    So a slice defined with ``table="colisions"`` loaded the wrong frame and
    said nothing. ``slice-row-count`` would then compute its expected value
    from that frame and mark a student's correct answer wrong.
    """
    typo = slices.Slice(
        "typo", "Typo", "colisions", None, lambda df: df["casualty_type"] == 1
    )
    monkeypatch.setitem(slices._BY_ID, "typo", typo)
    with pytest.raises(ValueError) as exc:
        slices.load("typo")
    message = str(exc.value)
    assert "colisions" in message
    assert "'collisions'" in message and "'casualties'" in message


def test_load_and_ksi_agree_about_which_table_names_are_real(monkeypatch):
    """One of the two rejected an unknown name and the other did not.

    That disagreement is what let the misspelling above through, so the two
    must reject the same names with the same words.
    """
    typo = slices.Slice(
        "typo", "Typo", "colisions", None, lambda df: df["casualty_type"] == 1
    )
    monkeypatch.setitem(slices._BY_ID, "typo", typo)
    with pytest.raises(ValueError) as from_load:
        slices.load("typo")
    with pytest.raises(ValueError) as from_ksi:
        slices.ksi(pd.DataFrame(), "colisions")
    assert str(from_load.value) == str(from_ksi.value)


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
