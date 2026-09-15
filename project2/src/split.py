"""
Time-based split. Data goes from 2025-01-07 to 2026-06-30 (about 18
months, 46,108 containers after cleaning).

Can't split randomly here - that would let future info leak into
training (e.g. a broker's later track record showing up while
predicting an earlier container). Splitting by arrived_on instead.

Cutoff: 2026-05-01
  - train/CV: 2025-01-07 to 2026-04-30 (~16 months, ~42k rows)
  - held-out: 2026-05-01 to 2026-06-30 (~2 months, ~3.8k rows, ~8%)

Picked this cutoff because it leaves enough held-out data to get a
stable read on precision at the ~60 containers/week the forwarder can
chase, while still keeping most of the data (and a full year cycle)
for actually building the model.
"""

from __future__ import annotations

import pandas as pd

CUTOFF_DATE = pd.Timestamp("2026-05-01")


def time_split(df: pd.DataFrame, cutoff: pd.Timestamp = CUTOFF_DATE):
    """Rows before cutoff -> train_cv, rows on/after -> held_out."""
    if not pd.api.types.is_datetime64_any_dtype(df["arrived_on"]):
        raise TypeError("arrived_on must be parsed to datetime before splitting")

    train_cv = df[df["arrived_on"] < cutoff].reset_index(drop=True)
    held_out = df[df["arrived_on"] >= cutoff].reset_index(drop=True)
    return train_cv, held_out


if __name__ == "__main__":
    df = pd.read_csv("data/processed/containers.csv", parse_dates=["arrived_on"])
    train_cv, held_out = time_split(df)
    print(f"train_cv: {len(train_cv)} rows, {train_cv['arrived_on'].min()} to {train_cv['arrived_on'].max()}")
    print(f"held_out: {len(held_out)} rows, {held_out['arrived_on'].min()} to {held_out['arrived_on'].max()}")
    print(f"train_cv delay rate: {train_cv['delayed'].mean():.3f}")
    print(f"held_out delay rate: {held_out['delayed'].mean():.3f}")
