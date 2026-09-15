"""
Stage A baselines. Two models on the raw columns, evaluated with
time respecting CV. These numbers are the floor everything else
(engineered features, tuning) gets compared against.

Columns I'm leaving out of every model, and why:
  container_id, vessel_id, importer_id, broker_id: just IDs, no
  signal on their own. Broker/importer history is a real feature
  but it's computed properly later with an expanding window, not
  just dumped in as a raw ID.

  arrived_on: not used raw. Calendar parts (day of week, month,
  weekend) get pulled out separately later.

  days_to_clear: left out. Not just because it's correlated with
  the target, it's only known once clearance is already done,
  meaning after the thing we're trying to predict has already
  happened. At the moment a container gets discharged, which is
  when this model actually needs to make a prediction, this number
  doesn't exist yet.

  delayed: that's the target.

Using XGBoost here since that's what the brief recommends.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier

from src.split import time_split

RAW_NUMERIC = ["hs_chapter", "gross_weight_kg", "declared_value_xaf"]
RAW_CATEGORICAL = ["container_type", "origin_port", "inspection_selected"]
# Not using goods_description here. It's free text standing in for
# hs_chapter, which is already in the feature set in structured form.
# Adding it would just be a high cardinality text column skewing the
# raw columns floor.
TARGET = "delayed"


def build_raw_pipeline() -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", "passthrough", RAW_NUMERIC),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                RAW_CATEGORICAL,
            ),
        ]
    )
    model = XGBClassifier(random_state=42, eval_metric="logloss")
    return Pipeline([("prep", preprocessor), ("model", model)])


def evaluate_with_time_cv(
    df: pd.DataFrame,
    feature_cols: list[str],
    build_pipeline,
    n_splits: int = 5,
) -> dict[str, list[float]]:
    """df needs to already be sorted by arrived_on. TimeSeriesSplit
    only ever trains on earlier folds and validates on a later one,
    so nothing from the future ends up in training.
    """
    df = df.sort_values("arrived_on").reset_index(drop=True)
    X = df[feature_cols]
    y = df[TARGET].values

    tscv = TimeSeriesSplit(n_splits=n_splits)
    roc_scores, pr_scores = [], []

    for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y[train_idx], y[val_idx]

        pipe = build_pipeline()
        pipe.fit(X_train, y_train)
        proba = pipe.predict_proba(X_val)[:, 1]

        roc = roc_auc_score(y_val, proba)
        pr = average_precision_score(y_val, proba)
        roc_scores.append(roc)
        pr_scores.append(pr)
        print(f"  fold {fold}: ROC-AUC={roc:.4f}  PR-AUC={pr:.4f}  (val n={len(val_idx)})")

    return {"roc_auc": roc_scores, "pr_auc": pr_scores}


def evaluate_majority_baseline(df: pd.DataFrame, n_splits: int = 5) -> dict[str, list[float]]:
    df = df.sort_values("arrived_on").reset_index(drop=True)
    y = df[TARGET].values
    tscv = TimeSeriesSplit(n_splits=n_splits)
    roc_scores, pr_scores = [], []

    for fold, (train_idx, val_idx) in enumerate(tscv.split(df)):
        y_train, y_val = y[train_idx], y[val_idx]
        clf = DummyClassifier(strategy="most_frequent")
        clf.fit(np.zeros((len(y_train), 1)), y_train)
        proba = clf.predict_proba(np.zeros((len(y_val), 1)))[:, 1]
        # Majority class predicts the same thing every time, so
        # ROC-AUC isn't really defined. It falls back to 0.5 by
        # convention. PR-AUC still tells us something vs the base rate.
        try:
            roc = roc_auc_score(y_val, proba)
        except ValueError:
            roc = 0.5
        pr = average_precision_score(y_val, proba)
        roc_scores.append(roc)
        pr_scores.append(pr)
        print(f"  fold {fold}: ROC-AUC={roc:.4f}  PR-AUC={pr:.4f}  (val n={len(val_idx)})")

    return {"roc_auc": roc_scores, "pr_auc": pr_scores}


def summarize(name: str, scores: dict[str, list[float]]) -> None:
    roc_mean, roc_std = np.mean(scores["roc_auc"]), np.std(scores["roc_auc"])
    pr_mean, pr_std = np.mean(scores["pr_auc"]), np.std(scores["pr_auc"])
    print(f"\n{name}")
    print(f"  ROC-AUC: {roc_mean:.4f} +/- {roc_std:.4f}")
    print(f"  PR-AUC:  {pr_mean:.4f} +/- {pr_std:.4f}")


if __name__ == "__main__":
    df = pd.read_csv("data/processed/containers.csv", parse_dates=["arrived_on"])
    train_cv, held_out = time_split(df)

    print("=== Baseline 1: majority class ===")
    majority_scores = evaluate_majority_baseline(train_cv)
    summarize("Majority class", majority_scores)

    print("\n=== Baseline 2: gradient boosting, raw columns, default settings ===")
    raw_feature_cols = RAW_NUMERIC + RAW_CATEGORICAL
    raw_scores = evaluate_with_time_cv(train_cv, raw_feature_cols, build_raw_pipeline)
    summarize("Gradient boosting (raw columns)", raw_scores)