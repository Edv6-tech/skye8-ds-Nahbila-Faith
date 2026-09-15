"""
The leakage test the brief requires in Stage B: a test that fails if
any container's own outcome enters its own feature.

The strategy: take a small synthetic dataset, flip one container's
own label (or its own value, for the value-density feature), and
check what changed.

- That container's OWN feature value must be unchanged. If it moved,
  its own outcome fed into its own history - a leak.
- Every LATER container of the same broker/importer/chapter SHOULD
  change, because the history genuinely did change for them. If
  nothing downstream reacts either, the feature isn't computing
  history at all, which is a different bug worth catching too.
- Every EARLIER container must also be unchanged, since a rate
  computed before an event happened can't depend on it.

This is stronger than eyeballing the formula, because it fails on
the exact bug class the brief warns about (own outcome -> own
feature) rather than on a hand-picked example that happens to look
right.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.features import (
    add_broker_history_features,
    add_importer_history_features,
    add_value_density_features,
)


def _toy_broker_frame() -> pd.DataFrame:
    # One broker, 5 containers, deliberately out of arrival order to
    # also exercise the internal sort.
    return pd.DataFrame(
        {
            "container_id": ["C3", "C1", "C2", "C5", "C4"],
            "arrived_on": pd.to_datetime(
                ["2025-01-03", "2025-01-01", "2025-01-02", "2025-01-05", "2025-01-04"]
            ),
            "broker_id": ["BK-001"] * 5,
            "importer_id": ["IM-001"] * 5,
            "delayed": [1, 0, 0, 1, 1],
        }
    )


@pytest.mark.parametrize(
    "history_fn,group_col,prefix",
    [
        (add_broker_history_features, "broker_id", "broker"),
        (add_importer_history_features, "importer_id", "importer"),
    ],
)
def test_history_feature_excludes_own_outcome(history_fn, group_col, prefix):
    baseline = _toy_broker_frame()
    mutated = baseline.copy()

    # Flip C2's own outcome (arrives 2025-01-02, the middle container).
    target_id = "C2"
    mutated.loc[mutated["container_id"] == target_id, "delayed"] ^= 1

    rate_col = f"{prefix}_delay_rate"

    out_baseline = history_fn(baseline).set_index("container_id")[rate_col]
    out_mutated = history_fn(mutated).set_index("container_id")[rate_col]

    earlier = ["C1"]  # arrived before C2
    later = ["C3", "C4", "C5"]  # arrived after C2, same broker/importer

    # The container whose own label we flipped must not see its own
    # rate change - if it does, its own outcome leaked into its own
    # feature.
    before = out_baseline.loc[target_id]
    after = out_mutated.loc[target_id]
    assert (before == after) or (pd.isna(before) and pd.isna(after)), (
        f"{prefix}_delay_rate for {target_id} changed when only {target_id}'s "
        "own label was flipped - its own outcome is leaking into its own "
        "feature."
    )

    # Earlier containers can't be affected by an event that hasn't
    # happened yet from their point of view.
    for cid in earlier:
        b, a = out_baseline.loc[cid], out_mutated.loc[cid]
        assert (b == a) or (pd.isna(b) and pd.isna(a)), (
            f"{prefix}_delay_rate for {cid} changed after flipping a LATER "
            "container's label - history feature is looking into the future."
        )

    # Later containers SHOULD change - if none of them do, the
    # feature isn't using history at all.
    changed_downstream = any(
        out_baseline.loc[cid] != out_mutated.loc[cid]
        and not (pd.isna(out_baseline.loc[cid]) and pd.isna(out_mutated.loc[cid]))
        for cid in later
    )
    assert changed_downstream, (
        f"Flipping {target_id}'s label changed nothing for later containers - "
        f"{prefix}_delay_rate does not appear to depend on history at all."
    )


def test_value_density_percentile_excludes_own_and_future_values():
    baseline = pd.DataFrame(
        {
            "container_id": ["C3", "C1", "C2", "C5", "C4"],
            "arrived_on": pd.to_datetime(
                ["2025-01-03", "2025-01-01", "2025-01-02", "2025-01-05", "2025-01-04"]
            ),
            "hs_chapter": [1, 1, 1, 1, 1],
            "declared_value_xaf": [300, 100, 200, 500, 400],
            "gross_weight_kg": [1, 1, 1, 1, 1],
        }
    )
    mutated = baseline.copy()

    # Blow up C4's own value - a huge change to a LATER container.
    target_id = "C4"
    mutated.loc[mutated["container_id"] == target_id, "declared_value_xaf"] = 10_000_000

    col = "value_per_kg_pct_in_chapter"
    out_baseline = add_value_density_features(baseline).set_index("container_id")[col]
    out_mutated = add_value_density_features(mutated).set_index("container_id")[col]

    earlier = ["C1", "C2", "C3"]  # all arrive before C4

    for cid in earlier:
        b, a = out_baseline.loc[cid], out_mutated.loc[cid]
        assert (b == a) or (pd.isna(b) and pd.isna(a)), (
            f"value_per_kg_pct_in_chapter for {cid} changed after a LATER "
            "container's value changed - this feature is leaking information "
            "from the future."
        )

    # C5 arrives after C4, so its percentile SHOULD move now that C4's
    # value is a huge outlier ahead of it.
    assert out_baseline.loc["C5"] != out_mutated.loc["C5"], (
        "Changing an earlier container's value had no effect on a later "
        "container's percentile - the feature does not appear to use "
        "history at all."
    )