"""Builds the engineered feature columns on top of the cleaned data
and writes the result back to data/processed/containers.csv.
Run this after clean.py and before comparison.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from features import (
    add_broker_history_features,
    add_calendar_features,
    add_congestion_features,
    add_importer_history_features,
    add_value_density_features,
    add_vessel_features,
)


def main():
    containers = pd.read_csv("data/processed/containers.csv", parse_dates=["arrived_on"])
    vessels = pd.read_csv("data/raw/vessels.csv", parse_dates=["arrived_on"])

    df = containers.sort_values("arrived_on").reset_index(drop=True)
    df = add_calendar_features(df)
    df = add_value_density_features(df)
    df = add_congestion_features(df)
    df = add_vessel_features(df, vessels)
    df = add_broker_history_features(df)
    df = add_importer_history_features(df)

    df.to_csv("data/processed/containers.csv", index=False)
    print(f"wrote {len(df)} rows, {len(df.columns)} columns to data/processed/containers.csv")


if __name__ == "__main__":
    main()