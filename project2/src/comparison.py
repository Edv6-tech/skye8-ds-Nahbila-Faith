
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline import build_pipeline
from split import cv_splits, time_split

TARGET = "delayed"

# Same raw columns as the Stage A floor.
# No engineered features, no history, no vessel or congestion or value density features.
# id columns are dropped and days_to_clear is dropped since it is basically the target.
RAW_CATEGORICAL = ["hs_chapter", "goods_description", "container_type", "origin_port"]
RAW_NUMERIC = ["gross_weight_kg", "declared_value_xaf"]
RAW_BOOL = ["inspection_selected"]


def build_raw_pipeline(random_state: int = 42) -> Pipeline:
    pre = ColumnTransformer(
        transformers=[
            (
                "cat",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        ("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                RAW_CATEGORICAL,
            ),
            ("num", SimpleImputer(strategy="median"), RAW_NUMERIC),
            (
                "bool",
                Pipeline(
                    [
                        ("to_float", FunctionTransformer(lambda X: X.astype("float64"))),
                        ("impute", SimpleImputer(strategy="most_frequent")),
                    ]
                ),
                RAW_BOOL,
            ),
        ]
    )
    return Pipeline([("pre", pre), ("model", HistGradientBoostingClassifier(random_state=random_state))])


def raw_floor_cv_scores(df: pd.DataFrame, n_splits: int = 5) -> dict:
    """Raw columns floor, checked on the same folds as the encoding comparison.
    This makes the gain a fair comparison, not just two different setups.
    """
    roc_scores, pr_scores = [], []
    for train_idx, val_idx in cv_splits(df, n_splits=n_splits):
        train_fold, val_fold = df.iloc[train_idx], df.iloc[val_idx]
        pipe = build_raw_pipeline()
        pipe.fit(train_fold, train_fold[TARGET])
        prob = pipe.predict_proba(val_fold)[:, 1]
        roc_scores.append(roc_auc_score(val_fold[TARGET], prob))
        pr_scores.append(average_precision_score(val_fold[TARGET], prob))
    return {
        "roc_auc_mean": float(np.mean(roc_scores)),
        "roc_auc_per_fold": [float(x) for x in roc_scores],
        "pr_auc_mean": float(np.mean(pr_scores)),
        "pr_auc_per_fold": [float(x) for x in pr_scores],
    }


def cv_scores(df: pd.DataFrame, high_card_encoding: str, n_splits: int = 5) -> dict:
    roc_scores, pr_scores = [], []
    for train_idx, val_idx in cv_splits(df, n_splits=n_splits):
        train_fold = df.iloc[train_idx]
        val_fold = df.iloc[val_idx]
        pipe = build_pipeline(high_card_encoding)
        pipe.fit(train_fold, train_fold[TARGET])
        prob = pipe.predict_proba(val_fold)[:, 1]
        roc_scores.append(roc_auc_score(val_fold[TARGET], prob))
        pr_scores.append(average_precision_score(val_fold[TARGET], prob))
    return {
        "roc_auc_mean": float(np.mean(roc_scores)),
        "roc_auc_per_fold": [float(x) for x in roc_scores],
        "pr_auc_mean": float(np.mean(pr_scores)),
        "pr_auc_per_fold": [float(x) for x in pr_scores],
    }


def run(processed_path: str = "data/processed/containers.csv") -> dict:
    df = pd.read_csv(processed_path, parse_dates=["arrived_on"])
    # held_out is never touched here, only train_cv is used
    train_cv, held_out = time_split(df)

    results = {"raw_floor_same_folds": raw_floor_cv_scores(train_cv)}
    for encoding in ("drop", "onehot", "target"):
        results[encoding] = cv_scores(train_cv, encoding)

    Path("artifacts").mkdir(exist_ok=True)
    with open("artifacts/stage_c_encoding_comparison.json", "w") as f:
        json.dump(results, f, indent=2)

    return results


def print_table(results: dict):
    print(f"{'set':<20} {'ROC AUC':>10} {'PR AUC':>10}")
    for name, r in results.items():
        print(f"{name:<20} {r['roc_auc_mean']:>10.4f} {r['pr_auc_mean']:>10.4f}")


if __name__ == "__main__":
    results = run()
    print_table(results)

    floor = results["raw_floor_same_folds"]["roc_auc_mean"]
    encodings = {k: v for k, v in results.items() if k != "raw_floor_same_folds"}
    best_encoding = max(encodings, key=lambda k: encodings[k]["roc_auc_mean"])
    gain = encodings[best_encoding]["roc_auc_mean"] - floor
    print()
    print(f"Engineered feature gain over raw floor, same folds: {gain:+.4f} ROC AUC ({best_encoding} encoding)")

    stage_a_path = Path("artifacts/stage_a_results.json")
    if stage_a_path.exists():
        stage_a = json.loads(stage_a_path.read_text())
        print(f"(Stage A single split floor for comparison: {stage_a['raw_gbm']['roc_auc']:.4f} ROC AUC)")