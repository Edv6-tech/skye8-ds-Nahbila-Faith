"""Stage B leakage tests.

Two things must be true of every history-style feature:
  1. A container's own outcome never enters its own feature.
  2. A same-day peer's outcome never enters another container's
     feature either - same day is not "earlier".

(1) is the test the brief explicitly requires. (2) is the subtler one
that a naive shift(1)-on-sorted-rows implementation passes silently
without actually satisfying - see the module docstring in features.py.
Both are checked here, for both broker and importer history and for
the chapter value-percentile feature, using synthetic data where the
right answer is known by construction.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from features import add_broker_history_features, add_importer_history_features, add_value_density_features


def _toy_containers():
    # Broker BK-001: two containers on day 1 (one delayed, one not),
    # one container on day 2. Broker BK-002: single container, day 1,
    # untouched control.
    return pd.DataFrame(
        {
            "container_id": ["C1", "C2", "C3", "C4"],
            "broker_id": ["BK-001", "BK-001", "BK-001", "BK-002"],
            "importer_id": ["IM-1", "IM-1", "IM-1", "IM-2"],
            "hs_chapter": [10, 10, 10, 20],
            "arrived_on": pd.to_datetime(
                ["2025-01-01", "2025-01-01", "2025-01-02", "2025-01-01"]
            ),
            "declared_value_xaf": [1000, 2000, 1500, 500],
            "gross_weight_kg": [10, 10, 10, 10],
            "delayed": [1, 0, 0, 0],
        }
    )


def test_own_outcome_never_enters_own_broker_feature():
    df = _toy_containers()
    out = add_broker_history_features(df)
    c1 = out[out["container_id"] == "C1"].iloc[0]
    # C1 is the first-ever container for BK-001: zero prior containers
    # regardless of its own outcome.
    assert c1["broker_prior_count"] == 0
    assert pd.isna(c1["broker_delay_rate"])

    # Flip C1's own outcome and confirm C1's own feature is unchanged.
    flipped = df.copy()
    flipped.loc[flipped["container_id"] == "C1", "delayed"] = 0
    out_flipped = add_broker_history_features(flipped)
    c1_flipped = out_flipped[out_flipped["container_id"] == "C1"].iloc[0]
    assert c1_flipped["broker_prior_count"] == c1["broker_prior_count"]
    assert pd.isna(c1_flipped["broker_delay_rate"]) == pd.isna(c1["broker_delay_rate"])


def test_same_day_peer_does_not_leak_into_broker_feature():
    df = _toy_containers()
    out = add_broker_history_features(df)
    c2 = out[out["container_id"] == "C2"].iloc[0]
    # C2 shares a day with C1 (delayed=1). If C1 leaked in, C2's prior
    # count would be 1 and its rate would be 1.0. It must instead see
    # zero prior containers, same as C1.
    assert c2["broker_prior_count"] == 0
    assert pd.isna(c2["broker_delay_rate"])


def test_next_day_container_sees_both_prior_day_containers():
    df = _toy_containers()
    out = add_broker_history_features(df)
    c3 = out[out["container_id"] == "C3"].iloc[0]
    # C3 arrives the day after C1 and C2, so it should see both of
    # them: 2 prior containers, 1 of which was delayed -> rate 0.5.
    assert c3["broker_prior_count"] == 2
    assert c3["broker_delay_rate"] == pytest.approx(0.5)


def test_other_broker_is_unaffected():
    df = _toy_containers()
    out = add_broker_history_features(df)
    c4 = out[out["container_id"] == "C4"].iloc[0]
    assert c4["broker_prior_count"] == 0
    assert pd.isna(c4["broker_delay_rate"])


def test_importer_history_same_day_no_leak():
    df = _toy_containers()
    out = add_importer_history_features(df)
    c1 = out[out["container_id"] == "C1"].iloc[0]
    c2 = out[out["container_id"] == "C2"].iloc[0]
    c3 = out[out["container_id"] == "C3"].iloc[0]
    assert c1["importer_prior_count"] == 0
    assert c2["importer_prior_count"] == 0
    assert c3["importer_prior_count"] == 2
    assert c3["importer_delay_rate"] == pytest.approx(0.5)


def test_value_percentile_same_day_ties_do_not_leak():
    # Same hs_chapter, same day, two different values. Neither should
    # be able to see the other - both get NaN (cold start), not a
    # percentile computed against each other.
    df = pd.DataFrame(
        {
            "hs_chapter": [10, 10, 10],
            "arrived_on": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-01-02"]),
            "declared_value_xaf": [100, 300, 200],
            "gross_weight_kg": [10, 10, 10],
        }
    )
    out = add_value_density_features(df)
    day1 = out[out["arrived_on"] == "2025-01-01"]
    assert day1["value_per_kg_pct_in_chapter"].isna().all()

    day2 = out[out["arrived_on"] == "2025-01-02"]
    # day2's value_per_kg is 20; day1 had values 10 and 30. 20 sits
    # strictly between them -> percentile 1/2 = 0.5.
    assert day2["value_per_kg_pct_in_chapter"].iloc[0] == pytest.approx(0.5)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))