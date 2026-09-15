"""
Stage B features, part 1: calendar features and value density.

Both of these only use information already sitting on the container's
own row (its arrival date, its weight, its declared value), so there's
no leakage risk here at all. The trickier features (broker/importer
history, congestion) come in later files.
"""

from __future__ import annotations

import pandas as pd


def add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    """Day of week, month, and a weekend flag, all pulled from
    arrived_on.
    """
    df = df.copy()
    df["arrival_day_of_week"] = df["arrived_on"].dt.dayofweek  # 0=Mon
    df["arrival_month"] = df["arrived_on"].dt.month
    df["arrival_is_weekend"] = df["arrived_on"].dt.dayofweek >= 5
    return df


def add_value_density_features(df: pd.DataFrame) -> pd.DataFrame:
    """Declared value per kg, and where this container sits in the
    value-per-kg distribution for its own HS chapter.

    The percentile is computed against the whole dataset here, not
    per fold, because it's describing the container's goods, not its
    outcome. It doesn't use the label at all, so there's nothing to
    leak from future rows the way there would be with a delay-history
    feature.
    """
    df = df.copy()
    df["value_per_kg"] = df["declared_value_xaf"] / df["gross_weight_kg"]
    df["value_per_kg_pct_in_chapter"] = df.groupby("hs_chapter")["value_per_kg"].rank(pct=True)
    return df