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


def add_congestion_features(df: pd.DataFrame) -> pd.DataFrame:
    """How busy the port was: how many containers arrived the same
    day, and how many arrived in the preceding 7 days (not counting
    today).

    Same-day count doesn't touch the label at all, just counts of
    arrivals, so there's no leakage risk in the sense that matters for
    this project. Trailing week count is shifted by one day so it
    only counts containers that arrived strictly before today, in
    keeping with the general rule that any history-style feature
    should only look backwards.
    """
    df = df.copy()

    daily_counts = df.groupby("arrived_on").size()

    all_dates = pd.date_range(daily_counts.index.min(), daily_counts.index.max())
    daily_counts_full = daily_counts.reindex(all_dates, fill_value=0)

    trailing_week = (
        daily_counts_full.rolling(window=7, min_periods=1)
        .sum()
        .shift(1)
        .fillna(0)
    )

    df["port_same_day_count"] = df["arrived_on"].map(daily_counts)
    df["port_trailing_week_count"] = df["arrived_on"].map(trailing_week)
    return df

def add_vessel_features(df: pd.DataFrame, vessels: pd.DataFrame) -> pd.DataFrame:
    """TEU discharged by the same vessel call, and this container's
    share of that call.

    Container type maps to TEU size (20ft types = 1 TEU, 40ft types
    = 2 TEU), so share = container_teu / vessel_teu_discharged.

    For the 220 rows flagged vessel_missing, the join has nothing to
    match, so these come out as NaN. That's expected and correct,
    not a bug, since there's genuinely no vessel data for them.
    """
    df = df.copy()
    df = df.merge(
        vessels[["vessel_id", "teu_discharged"]],
        on="vessel_id",
        how="left",
    )
    df["container_teu"] = df["container_type"].str.startswith("40").map({True: 2, False: 1})
    df["vessel_teu_share"] = df["container_teu"] / df["teu_discharged"]
    return df