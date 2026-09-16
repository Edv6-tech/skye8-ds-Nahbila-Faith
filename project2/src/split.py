"""
Time-based split. Data goes from 2025-01-07 to 2026-06-30, about 18
months, 46,108 containers after cleaning.

Can't split randomly here, that would let future info leak into
training (e.g. a broker's later track record showing up while
predicting an earlier container). Splitting by arrived_on instead.

Cutoff: 2026-05-01
  train/CV: 2025-01-07 to 2026-04-30 (about 16 months, about 42k rows)
  held out: 2026-05-01 to 2026-06-30 (about 2 months, about 3.8k rows, about 8%)

Picked this cutoff because it leaves enough held out data to get a
stable read on precision at the roughly 60 containers a week the
forwarder can chase, while still keeping most of the data, including
a full year cycle, for actually building the model.
"""

from __future__ import annotations

import pandas as pd
from sklearn.model_selection import TimeSeriesSplit

CUTOFF_DATE = pd.Timestamp("2026-05-01")


def time_split(df: pd.DataFrame, cutoff: pd.Timestamp = CUTOFF_DATE):
    """Rows before cutoff go to train_cv, rows on or after go to
    held_out. Sorts by arrived_on first - the raw CSV is not in
    chronological order, and anything built on top of this split
    (cross-validation, expanding-window features) needs train_cv to
    actually be in time order, not just correctly filtered.
    """
    if not pd.api.types.is_datetime64_any_dtype(df["arrived_on"]):
        raise TypeError("arrived_on must be parsed to datetime before splitting")

    df = df.sort_values("arrived_on").reset_index(drop=True)
    train_cv = df[df["arrived_on"] < cutoff].reset_index(drop=True)
    held_out = df[df["arrived_on"] >= cutoff].reset_index(drop=True)
    return train_cv, held_out


def cv_splits(train_cv: pd.DataFrame, n_splits: int = 5):
    """Yields (train_idx, val_idx) pairs for cross-validation within
    train_cv only - never call this on the full df, only on the
    train_cv half of time_split's output.

    Splits on UNIQUE DATES rather than raw row position. Thousands of
    containers share the same arrived_on, and TimeSeriesSplit run
    directly on rows draws its fold boundary by row count, which can
    land in the middle of a day and put same-date containers on both
    sides of a fold. Splitting the date axis first and mapping rows
    back by date keeps every fold boundary a clean calendar cut, so
    no container's fold assignment depends on where it happened to
    sit among same-day rows.

    Assumes train_cv is already sorted by arrived_on ascending, which
    is guaranteed if it came straight out of time_split.
    """
    if not train_cv["arrived_on"].is_monotonic_increasing:
        raise ValueError(
            "train_cv must be sorted by arrived_on before calling "
            "cv_splits - pass it the output of time_split directly."
        )

    unique_dates = train_cv["arrived_on"].drop_duplicates().reset_index(drop=True)
    tss = TimeSeriesSplit(n_splits=n_splits)

    for date_train_idx, date_val_idx in tss.split(unique_dates):
        train_dates = set(unique_dates.iloc[date_train_idx])
        val_dates = set(unique_dates.iloc[date_val_idx])
        train_idx = train_cv.index[train_cv["arrived_on"].isin(train_dates)].to_numpy()
        val_idx = train_cv.index[train_cv["arrived_on"].isin(val_dates)].to_numpy()
        yield train_idx, val_idx


if __name__ == "__main__":
    df = pd.read_csv("data/processed/containers.csv", parse_dates=["arrived_on"])
    train_cv, held_out = time_split(df)
    print(f"train_cv: {len(train_cv)} rows, {train_cv['arrived_on'].min()} to {train_cv['arrived_on'].max()}")
    print(f"held_out: {len(held_out)} rows, {held_out['arrived_on'].min()} to {held_out['arrived_on'].max()}")
    print(f"train_cv delay rate: {train_cv['delayed'].mean():.3f}")
    print(f"held_out delay rate: {held_out['delayed'].mean():.3f}")

    print()
    for i, (tr_idx, val_idx) in enumerate(cv_splits(train_cv)):
        tr_dates = train_cv.loc[tr_idx, "arrived_on"]
        val_dates = train_cv.loc[val_idx, "arrived_on"]
        print(
            f"fold {i}: train ends {tr_dates.max().date()}, "
            f"val {val_dates.min().date()}..{val_dates.max().date()} "
            f"(n_train={len(tr_idx)}, n_val={len(val_idx)})"
        )