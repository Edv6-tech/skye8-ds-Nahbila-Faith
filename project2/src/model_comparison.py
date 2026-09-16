
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline import build_pipeline
from split import cv_splits, time_split

TARGET = "delayed"
ENCODING = "onehot"

MODELS = {
    "gbm": HistGradientBoostingClassifier(random_state=42),
    "random_forest": RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1),
    "logistic_regression": LogisticRegression(max_iter=1000),
}


def cv_scores_for_model(df: pd.DataFrame, model, n_splits: int = 5) -> dict:
    roc_scores, pr_scores = [], []
    t0 = time.time()
    for train_idx, val_idx in cv_splits(df, n_splits=n_splits):
        train_fold, val_fold = df.iloc[train_idx], df.iloc[val_idx]
        pipe = build_pipeline(ENCODING, model=model)
        pipe.fit(train_fold, train_fold[TARGET])
        prob = pipe.predict_proba(val_fold)[:, 1]
        roc_scores.append(roc_auc_score(val_fold[TARGET], prob))
        pr_scores.append(average_precision_score(val_fold[TARGET], prob))
    elapsed = time.time() - t0
    return {
        "roc_auc_mean": float(np.mean(roc_scores)),
        "pr_auc_mean": float(np.mean(pr_scores)),
        "seconds": round(elapsed, 1),
    }


def run(processed_path: str = "data/processed/containers.csv") -> dict:
    df = pd.read_csv(processed_path, parse_dates=["arrived_on"])
    train_cv, held_out = time_split(df)

    results = {}
    for name, model in MODELS.items():
        results[name] = cv_scores_for_model(train_cv, model)

    Path("artifacts").mkdir(exist_ok=True)
    with open("artifacts/stage_d_model_comparison.json", "w") as f:
        json.dump(results, f, indent=2)
    return results


def print_table(results: dict):
    print(f"{'model':<22} {'ROC AUC':>10} {'PR AUC':>10} {'seconds':>10}")
    for name, r in results.items():
        print(f"{name:<22} {r['roc_auc_mean']:>10.4f} {r['pr_auc_mean']:>10.4f} {r['seconds']:>10.1f}")


if __name__ == "__main__":
    results = run()
    print_table(results)