import numpy as np
import pandas as pd
import pytest
from make_synthetic import (
    FAULTS,
    SEED,
    UnknownFaultError,
    make_leaky_split,
    make_sensor_series,
    write_all,
)

from cwai import registry


def test_same_seed_gives_identical_output():
    assert make_sensor_series(days=30).equals(make_sensor_series(days=30))


def test_different_seed_gives_different_output():
    a = make_sensor_series(days=30, seed=1)
    b = make_sensor_series(days=30, seed=2)
    assert not a.flow.equals(b.flow)


def test_seed_constant_is_the_agreed_value():
    assert SEED == 20261125


def test_columns_and_hourly_spacing():
    df = make_sensor_series(days=10)
    assert list(df.columns) == ["timestamp", "flow", "sensor_id"]
    assert len(df) == 240
    assert (df.timestamp.diff().dropna() == pd.Timedelta(hours=1)).all()


def test_clean_series_has_no_missing_flow():
    assert make_sensor_series(days=30).flow.notna().all()


def test_weekday_morning_peak_exceeds_small_hours():
    df = make_sensor_series(days=60)
    hourly = df.groupby(df.timestamp.dt.hour).flow.mean()
    assert hourly[8] > hourly[3] * 2


def test_weekday_has_evening_peak_and_weekend_is_flatter():
    df = make_sensor_series(days=84)
    weekday = (
        df[df.timestamp.dt.day_of_week < 5].groupby(df.timestamp.dt.hour).flow.mean()
    )
    weekend = (
        df[df.timestamp.dt.day_of_week >= 5].groupby(df.timestamp.dt.hour).flow.mean()
    )
    assert weekday[17] > weekday[12] * 1.2
    assert weekday[8] > weekday[12] * 1.2
    assert weekend[8] < weekday[8] * 0.7


def test_overnight_dropout_nulls_only_night_hours():
    df = make_sensor_series(days=30, faults=("overnight_dropout",))
    missing_hours = set(df[df.flow.isna()].timestamp.dt.hour)
    assert missing_hours and missing_hours <= {0, 1, 2, 3, 4}


def test_shift_midyear_changes_mean_across_halves():
    df = make_sensor_series(days=365, faults=("shift_midyear",))
    first, second = df.flow[: len(df) // 2].mean(), df.flow[len(df) // 2 :].mean()
    assert abs(second - first) > first * 0.2


def test_stuck_sensor_produces_a_long_constant_run():
    df = make_sensor_series(days=60, faults=("stuck_sensor",))
    run = (df.flow != df.flow.shift()).cumsum()
    assert run.value_counts().max() >= 24


def test_clean_series_has_no_long_constant_run():
    df = make_sensor_series(days=60)
    run = (df.flow != df.flow.shift()).cumsum()
    assert run.value_counts().max() < 5


def test_faults_compose_without_undoing_each_other():
    clean = make_sensor_series(days=365)
    both = make_sensor_series(days=365, faults=tuple(sorted(FAULTS)))
    assert both.flow.isna().any()  # dropout survived stuck_sensor and shift
    assert set(both[both.flow.isna()].timestamp.dt.hour) <= {0, 1, 2, 3, 4}
    observed = both.flow.dropna()  # dropout may punctuate the stuck run
    run = (observed != observed.shift()).cumsum()
    assert run.value_counts().max() >= 24  # stuck run survived the shift
    half = len(both) // 2
    assert both.flow[half:].mean() > clean.flow[half:].mean() * 1.2  # shift survived


def test_fault_order_does_not_matter():
    a = make_sensor_series(days=90, faults=("stuck_sensor", "overnight_dropout"))
    b = make_sensor_series(days=90, faults=("overnight_dropout", "stuck_sensor"))
    assert a.equals(b)


def test_faults_do_not_change_timestamps():
    clean = make_sensor_series(days=30)
    faulty = make_sensor_series(days=30, faults=tuple(FAULTS))
    assert clean.timestamp.equals(faulty.timestamp)


def test_unknown_fault_lists_available_faults():
    with pytest.raises(UnknownFaultError) as exc:
        make_sensor_series(faults=("not-a-fault",))
    assert "overnight_dropout" in str(exc.value)
    assert isinstance(exc.value, ValueError)


def test_fault_names_are_the_agreed_set():
    assert FAULTS == frozenset({"overnight_dropout", "shift_midyear", "stuck_sensor"})


def test_leaky_split_shares_timestamps_between_train_and_test():
    train, test = make_leaky_split(make_sensor_series(days=60))
    assert set(train.timestamp) & set(test.timestamp)


def test_leaky_split_overlap_is_substantial_and_deterministic():
    df = make_sensor_series(days=60)
    train, test = make_leaky_split(df)
    shared = set(train.timestamp) & set(test.timestamp)
    assert len(shared) > 0.5 * len(test)
    train2, test2 = make_leaky_split(df)
    assert train.equals(train2) and test.equals(test2)


def test_write_all_uses_registry_paths_and_is_byte_identical(tmp_path):
    first = write_all(tmp_path / "a")
    second = write_all(tmp_path / "b")
    expected = {
        registry.get("sensor-clean").relpath,
        registry.get("sensor-faulty").relpath,
    }
    assert {str(p.relative_to(tmp_path / "a")) for p in first} == expected
    for p, q in zip(first, second, strict=True):
        assert p.read_bytes() == q.read_bytes()
    clean = pd.read_parquet(first[0])
    faulty = pd.read_parquet(first[1])
    assert clean.flow.notna().all()
    assert faulty.flow.isna().any()
    assert np.isclose(len(clean), 8760)
