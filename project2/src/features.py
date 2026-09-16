"""
Stage B features: calendar features, value density, congestion,
vessel features, and broker/importer history.

All "prior" features here are computed by DAY, not by row. Sorting by
arrived_on alone only fixes the order between different days - it does
nothing about the order of containers that share a day, and that order
is arbitrary (whatever position they happened to land in after a
stable sort of the raw CSV). Two containers from the same broker
discharged on the same day are not "earlier" than each other, so
neither may see the other's outcome. Batching by day - compute every
same-day row's feature from the state as of the END of the PREVIOUS
day, then fold the whole day's values in at once - is what makes that
true regardless of row order within the day. A per-row incremental
loop (process row 1, insert row 1, process row 2, ...) looks like it
respects time order but actually leaks across same-day ties; this bit
us once already in the CV splitter (fixed by splitting on unique dates
instead of row position) and applies here for exactly the same reason.
"""

from __future__ import annotations

import bisect

import numpy as np
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
    value-per-kg distribution for its own HS chapter, using only
    chapter-mates that arrived on a STRICTLY EARLIER day.

    Batched by day: every container that arrived on the same day gets
    its percentile computed against the same "seen" set - whatever
    values had accumulated through the end of the previous day - and
    only after every same-day row has been scored do that day's own
    values get folded into "seen" for the next day. This is what
    keeps same-day chapter-mates from leaking into each other, which
    a row-by-row incremental version (insert immediately after each
    row) would not: with 92% of chapter-days holding more than one
    container, that gap would fire on almost every group.

    Requires df to already be sorted by arrived_on before this is
    called, or it sorts internally and returns rows in that order.
    """
    df = df.sort_values("arrived_on").copy()
    df["value_per_kg"] = df["declared_value_xaf"] / df["gross_weight_kg"]

    def _prior_percentile_by_day(group: pd.DataFrame) -> pd.Series:
        seen: list[float] = []
        out = pd.Series(index=group.index, dtype="float64")
        for _, day_rows in group.groupby("arrived_on", sort=True):
            n = len(seen)
            if n == 0:
                # first day this chapter has any data - cold start,
                # same treatment as broker/importer history with zero
                # prior containers.
                out.loc[day_rows.index] = float("nan")
            else:
                out.loc[day_rows.index] = [
                    bisect.bisect_left(seen, v) / n for v in day_rows["value_per_kg"]
                ]
            # fold the whole day in at once, only after every row in
            # it has already been scored against the pre-day state.
            for v in day_rows["value_per_kg"]:
                bisect.insort(seen, v)
        return out

    pct = pd.Series(index=df.index, dtype="float64")
    for _, chapter_rows in df.groupby("hs_chapter"):
        pct.loc[chapter_rows.index] = _prior_percentile_by_day(chapter_rows)
    df["value_per_kg_pct_in_chapter"] = pct
    return df


def add_congestion_features(df: pd.DataFrame) -> pd.DataFrame:
    """How busy the port was: how many containers arrived the same
    day, and how many arrived in the preceding 7 days (not counting
    today).

    This one was already day-batched in the original version (it
    works off `daily_counts`, a per-date aggregate, from the start)
    so it doesn't have the same-day-tie problem the history features
    had. Same-day count doesn't touch the label at all, just counts
    of arrivals. Trailing week count is shifted by one day so it only
    counts containers that arrived strictly before today.
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
    arrived on a STRICTLY EARLIER day than the one being scored.

    Aggregated to (group_col, arrived_on) first, so every row sharing
    a group and a day is guaranteed to see the identical prior state -
    whatever had accumulated through the end of the previous day that
    group had any activity. This is deliberately NOT a per-row
    expanding().shift(1): that only drops the current *row* from the
    window, which stops a container's own outcome from entering its
    own feature (the test the brief requires), but does nothing about
    a same-day sibling row's outcome entering the window - and with
    65% of broker-days holding more than one container, that gap
    would fire constantly. Aggregating to the day level first closes
    it, because the shift then operates on whole days, not rows.

    df must already be sorted by arrived_on (callers are responsible
    for this, since both broker and importer history need the same
    sort and we don't want to pay for it twice).
    """
    daily = (
        df.groupby([group_col, "arrived_on"])["delayed"]
        .agg(day_count="count", day_sum="sum")
        .reset_index()
        .sort_values([group_col, "arrived_on"])
    )

    grouped = daily.groupby(group_col)
    daily["prior_count"] = grouped["day_count"].cumsum() - daily["day_count"]
    daily["prior_sum"] = grouped["day_sum"].cumsum() - daily["day_sum"]

    # rate is undefined with zero prior containers - leave NaN and let
    # the pipeline's imputer handle cold start with a global prior,
    # rather than silently coding it as 0 (which would say "never
    # delayed" for brokers/importers we simply have no history on).
    safe_denominator = daily["prior_count"].astype("float64").replace(0.0, np.nan)
    daily[f"{prefix}_delay_rate"] = daily["prior_sum"] / safe_denominator
    daily = daily.rename(columns={"prior_count": f"{prefix}_prior_count"})

    df = df.merge(
        daily[[group_col, "arrived_on", f"{prefix}_prior_count", f"{prefix}_delay_rate"]],
        on=[group_col, "arrived_on"],
        how="left",
    )
    return df


def add_broker_history_features(df: pd.DataFrame) -> pd.DataFrame:
    """Broker's delay rate over strictly-earlier-day containers, plus
    how many containers that estimate rests on.
    """
    df = df.sort_values("arrived_on").copy()
    return _add_expanding_history(df, "broker_id", "broker")


def add_importer_history_features(df: pd.DataFrame) -> pd.DataFrame:
    """Same as broker history, for importers."""
    df = df.sort_values("arrived_on").copy()
    return _add_expanding_history(df, "importer_id", "importer")