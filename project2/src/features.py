"""
Stage B features, part 1: calendar features, value density, congestion,
and vessel features.

Broker/importer history (the highest-signal but highest-risk features)
come in a later file, alongside the leakage test.
"""

from __future__ import annotations

import bisect

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

    This percentile IS a history feature, even though it doesn't touch
    the label: a container's rank must only be computed against
    chapter-mates that arrived earlier. Ranking against the whole
    dataset (including containers that arrive months later) leaks
    information from the future into the past, the same way an
    unshifted broker delay-rate would - it just doesn't use the label,
    so it's easy to miss.

    NOTE on an earlier, subtly wrong version of this fix: computing
    `.expanding().rank(pct=True)` and then `.shift(1)`-ing the
    *result* does not do what it looks like it does. That shifts an
    already-computed number down one row, so row i ends up with row
    i-1's rank of row i-1's OWN value - not row i's value ranked
    against its own priors. It happens to look right on monotonically
    increasing data (which is why a quick synthetic check missed it),
    but it isn't actually using each row's own value at all.

    The shift-then-aggregate trick used for broker/importer history
    works there because sum/mean are pure aggregates of the past.
    Rank doesn't have that property: it needs the current row's own
    value plugged into a window of *only* prior values, which is an
    online computation, not a shift. Hence the explicit incremental
    version below.

    Requires df to already be sorted by arrived_on before this is
    called, or it sorts internally and returns rows in that order.
    """
    df = df.sort_values("arrived_on").copy()
    df["value_per_kg"] = df["declared_value_xaf"] / df["gross_weight_kg"]

    def _prior_percentile(s: pd.Series) -> pd.Series:
        seen: list[float] = []
        out = []
        for v in s:
            if seen:
                # fraction of strictly-prior values below this one
                out.append(bisect.bisect_left(seen, v) / len(seen))
            else:
                # first container in the chapter has no prior values
                # to compare against - cold start, same as broker/
                # importer history with zero prior containers.
                out.append(float("nan"))
            bisect.insort(seen, v)
        return pd.Series(out, index=s.index)

    df["value_per_kg_pct_in_chapter"] = (
        df.groupby("hs_chapter")["value_per_kg"]
        .apply(_prior_percentile)
        .reset_index(level=0, drop=True)
    )
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


def _add_expanding_history(
    df: pd.DataFrame, group_col: str, prefix: str
) -> pd.DataFrame:
    """Shared logic for broker and importer history: an expanding
    delay rate and a supporting count, using only containers that
    arrived strictly before the one being scored.

    df must already be sorted by arrived_on (callers are responsible
    for this, since both broker and importer history need the same
    sort and we don't want to pay for it twice).

    The shift(1) is what keeps a container's own outcome out of its
    own feature: expanding().sum() / expanding().count() computed on
    'delayed' *up to and including* the current row would let a
    container's own label leak into its own rate. Shifting by one
    row (within the group) drops the current row from the window
    before computing anything.
    """
    grouped = df.groupby(group_col)["delayed"]
    prior_count = grouped.cumcount()
    prior_sum = grouped.apply(lambda s: s.shift(1).expanding().sum()).reset_index(
        level=0, drop=True
    )

    df[f"{prefix}_prior_count"] = prior_count
    # rate is undefined with zero prior containers - leave NaN and let
    # the pipeline's imputer handle cold start with a global prior,
    # rather than silently coding it as 0 (which would say "never
    # delayed" for brokers/importers we simply have no history on).
    import numpy as np

    safe_denominator = prior_count.astype("float64").replace(0.0, np.nan)
    df[f"{prefix}_delay_rate"] = prior_sum / safe_denominator
    return df


def add_broker_history_features(df: pd.DataFrame) -> pd.DataFrame:
    """Broker's delay rate over strictly-earlier containers, plus how
    many containers that estimate rests on.
    """
    df = df.sort_values("arrived_on").copy()
    return _add_expanding_history(df, "broker_id", "broker")


def add_importer_history_features(df: pd.DataFrame) -> pd.DataFrame:
    """Same as broker history, for importers."""
    df = df.sort_values("arrived_on").copy()
    return _add_expanding_history(df, "importer_id", "importer")