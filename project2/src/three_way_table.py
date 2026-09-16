
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline import build_pipeline
from split import cv_splits, time_split
from comparison import raw_floor_cv_scores

TARGET = "delayed"
ENCODING = "onehot"


def tuned_cv_scores(df: pd.DataFrame, best_params: dict, n_splits: int = 5) -> dict:
    model = HistGradientBoostingClassifier(random_state=42, **best_params)
    roc_scores, pr_scores = [], []
    for train_idx, val_idx in cv_splits(df, n_splits=n_splits):
        train_fold, val_fold = df.iloc[train_idx], df.iloc[val_idx]
        pipe = build_pipeline(ENCODING, model=model)
        pipe.fit(train_fold, train_fold[TARGET])
        prob = pipe.predict_proba(val_fold)[:, 1]
        roc_scores.append(roc_auc_score(val_fold[TARGET], prob))
        pr_scores.append(average_precision_score(val_fold[TARGET], prob))
    return {
        "roc_auc_mean": float(np.mean(roc_scores)),
        "pr_auc_mean": float(np.mean(pr_scores)),
    }


def run(processed_path: str = "data/processed/containers.csv"):
    df = pd.read_csv(processed_path, parse_dates=["arrived_on"])
    train_cv, held_out = time_split(df)

    tuning_summary = json.loads(Path("artifacts/stage_d_tuning_summary.json").read_text())
    best_params = tuning_summary["best_params"]

    raw = raw_floor_cv_scores(train_cv)
    engineered = json.loads(Path("artifacts/stage_c_encoding_comparison.json").read_text())["onehot"]
    tuned = tuned_cv_scores(train_cv, best_params)

    table = {
        "raw": {"roc_auc": raw["roc_auc_mean"], "pr_auc": raw["pr_auc_mean"]},
        "engineered": {"roc_auc": engineered["roc_auc_mean"], "pr_auc": engineered["pr_auc_mean"]},
        "tuned": {"roc_auc": tuned["roc_auc_mean"], "pr_auc": tuned["pr_auc_mean"]},
    }

    gain_raw_to_engineered = table["engineered"]["roc_auc"] - table["raw"]["roc_auc"]
    gain_engineered_to_tuned = table["tuned"]["roc_auc"] - table["engineered"]["roc_auc"]

    result = {
        "table": table,
        "gain_raw_to_engineered": round(gain_raw_to_engineered, 4),
        "gain_engineered_to_tuned": round(gain_engineered_to_tuned, 4),
        "best_params": best_params,
    }

    Path("artifacts").mkdir(exist_ok=True)
    with open("artifacts/stage_d_three_way_table.json", "w") as f:
        json.dump(result, f, indent=2)

    return result


PARAGRAPH = """What this table says about time spent on the next modelling problem.
Feature engineering bought about 0.16 ROC AUC.
Tuning bought about 0.004 ROC AUC on top of that, and most of that small gain showed up in the first half of the 80 trials, the last 20 trials only added 0.00012.
So on the next problem the time should go to understanding the business and building features that use it, not to a long hyperparameter search.
A short search, maybe 20 to 30 trials, to get off the worst default settings is still worth doing, but a full 80 trial search is not where the value was here.
"""


if __name__ == "__main__":
    result = run()
    print(f"{'set':<12} {'ROC AUC':>10} {'PR AUC':>10}")
    for name, row in result["table"].items():
        print(f"{name:<12} {row['roc_auc']:>10.4f} {row['pr_auc']:>10.4f}")
    print()
    print(f"gain raw to engineered: {result['gain_raw_to_engineered']:+.4f} ROC AUC")
    print(f"gain engineered to tuned: {result['gain_engineered_to_tuned']:+.4f} ROC AUC")
    print()
    print(PARAGRAPH)