"""Seeded synthetic traffic-sensor data with optional planted faults.

Real data supplies whatever bugs it happens to contain. Generated data lets a
lesson plant exactly the failure it needs: the faults below are unmistakably
present when requested and absent otherwise. Output is deterministic for a
given seed.

Run ``python scripts/make_synthetic.py`` to (re)write the two committed files.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from cwai import registry

SEED = 20261125

FAULTS = frozenset({"overnight_dropout", "shift_midyear", "stuck_sensor"})

# Fixed per-fault stream numbers: each fault draws from its own generator, so
# the result does not depend on which other faults are requested or in what
# order they were listed.
_FAULT_STREAM = {"overnight_dropout": 1, "shift_midyear": 2, "stuck_sensor": 3}
# Faults are applied in this order. Dropout goes last so a missing value is
# never overwritten; stuck and shift only ever touch values that exist.
_APPLY_ORDER = ("shift_midyear", "stuck_sensor", "overnight_dropout")

_START = "2024-01-01"  # a Monday
_SENSOR_ID = "A58-0042"
_NIGHT_HOURS = (0, 1, 2, 3, 4)
_DROPOUT_NIGHT_PROBABILITY = 0.35
_SHIFT_FACTOR = 1.35
_STUCK_HOURS = 96


class UnknownFaultError(ValueError):
    """Raised when a requested fault is not one of ``FAULTS``."""


def _profile(timestamps: pd.DatetimeIndex) -> np.ndarray:
    """Expected hourly flow: weekday twin peaks, flatter weekend hump."""
    hour = timestamps.hour.to_numpy().astype(float)
    weekend = timestamps.day_of_week.to_numpy() >= 5
    daytime = np.exp(-((hour - 13) ** 2) / (2 * 5.0**2))
    morning = np.exp(-((hour - 8) ** 2) / (2 * 1.2**2))
    evening = np.exp(-((hour - 17) ** 2) / (2 * 1.5**2))
    weekday_flow = 40 + 140 * daytime + 400 * morning + 380 * evening
    weekend_flow = 30 + 200 * np.exp(-((hour - 13) ** 2) / (2 * 4.0**2))
    return np.where(weekend, weekend_flow, weekday_flow)


def _fault_rng(seed: int, fault: str) -> np.random.Generator:
    return np.random.default_rng([seed, _FAULT_STREAM[fault]])


def _shift_midyear(flow: np.ndarray, seed: int) -> None:
    flow[len(flow) // 2 :] *= _SHIFT_FACTOR


def _stuck_sensor(flow: np.ndarray, seed: int) -> None:
    """Freeze the reading at one value for a few days in the first half."""
    n = len(flow)
    length = min(_STUCK_HOURS, max(n // 4, 2))
    rng = _fault_rng(seed, "stuck_sensor")
    start = int(rng.integers(n // 10, max(n // 2 - length, n // 10 + 1)))
    flow[start : start + length] = flow[start]


def _overnight_dropout(flow: np.ndarray, seed: int) -> None:
    """Lose 00:00-04:59 on a random subset of nights (at least one)."""
    rng = _fault_rng(seed, "overnight_dropout")
    nights = len(flow) // 24
    hit = rng.random(nights) < _DROPOUT_NIGHT_PROBABILITY
    if not hit.any():
        hit[int(rng.integers(nights))] = True
    for night in np.flatnonzero(hit):
        flow[night * 24 + _NIGHT_HOURS[0] : night * 24 + _NIGHT_HOURS[-1] + 1] = np.nan


_FAULT_FUNCS = {
    "shift_midyear": _shift_midyear,
    "stuck_sensor": _stuck_sensor,
    "overnight_dropout": _overnight_dropout,
}


def make_sensor_series(
    days: int = 365, faults: tuple[str, ...] = (), seed: int = SEED
) -> pd.DataFrame:
    """Hourly flow for one count site, optionally with planted faults."""
    unknown = sorted(set(faults) - FAULTS)
    if unknown:
        raise UnknownFaultError(
            f"Unknown fault(s) {unknown}; available faults: {sorted(FAULTS)}"
        )

    timestamps = pd.date_range(_START, periods=days * 24, freq="h")
    rng = np.random.default_rng(seed)
    noise = rng.lognormal(mean=0.0, sigma=0.08, size=len(timestamps))
    flow = np.round(_profile(timestamps) * noise, 1)

    for fault in _APPLY_ORDER:
        if fault in faults:
            _FAULT_FUNCS[fault](flow, seed)

    return pd.DataFrame(
        {"timestamp": timestamps, "flow": flow, "sensor_id": _SENSOR_ID}
    )


def make_leaky_split(
    df: pd.DataFrame, seed: int = SEED
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """A split that looks respectable and is contaminated.

    Train is a random 80% of rows. Test is an independent random 20% of *all*
    rows, so most test timestamps also appear in train. A model evaluated on it
    scores well because it has seen the answers, not because it learned anything.
    """
    rng = np.random.default_rng([seed, 99])
    n = len(df)
    train_idx = np.sort(rng.choice(n, size=int(n * 0.8), replace=False))
    test_idx = np.sort(rng.choice(n, size=int(n * 0.2), replace=False))
    return df.iloc[train_idx].reset_index(drop=True), df.iloc[test_idx].reset_index(
        drop=True
    )


def write_all(root: Path | None = None) -> list[Path]:
    """Write the clean and faulty files under ``root`` (default: the data dir).

    Paths come from the registry. Returns [clean_path, faulty_path].
    """
    root = registry.data_root() if root is None else Path(root)
    variants = {
        "sensor-clean": make_sensor_series(),
        "sensor-faulty": make_sensor_series(faults=tuple(sorted(FAULTS))),
    }
    paths = []
    for key, frame in variants.items():
        path = root / registry.get(key).relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path, index=False)
        paths.append(path)
    return paths


if __name__ == "__main__":
    for written in write_all():
        print(f"wrote {written} ({written.stat().st_size} bytes)")
