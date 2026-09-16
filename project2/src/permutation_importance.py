
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline import build_pipeline
from split import cv_splits, time_split

TARGET = "delayed"
ENCODING = "onehot"


def run(processed_path: str = "data/processed/containers.csv"):
    df = pd.read_csv(processed_path, parse_dates=["arrived_on"])
    train_cv, held_out = time_split(df)

    tuning_summary = json.loads(Path("artifacts/stage_d_tuning_summary.json").read_text())
    best_params = tuning_summary["best_params"]

    folds = list(cv_splits(train_cv, n_splits=5))
    train_idx, val_idx = folds[-1]
    train_fold, val_fold = train_cv.iloc[train_idx], train_cv.iloc[val_idx]

    model = HistGradientBoostingClassifier(random_state=42, **best_params)
    pipe = build_pipeline(ENCODING, model=model)
    pipe.fit(train_fold, train_fold[TARGET])

    val_X = val_fold.drop(columns=[TARGET])
    val_y = val_fold[TARGET]

    result = permutation_importance(
        pipe,
        val_X,
        val_y,
        n_repeats=10,
        random_state=42,
        scoring="roc_auc",
        n_jobs=-1,
    )

    feature_names = list(val_X.columns)
    rows = sorted(
        (
            {"feature": name, "importance_mean": float(m), "importance_std": float(s)}
            for name, m, s in zip(feature_names, result.importances_mean, result.importances_std)
        ),
        key=lambda r: r["importance_mean"],
        reverse=True,
    )

    Path("artifacts").mkdir(exist_ok=True)
    with open("artifacts/stage_d_permutation_importance.json", "w") as f:
        json.dump(rows, f, indent=2)

    return rows


if __name__ == "__main__":
    rows = run()
    print(f"{'feature':<32} {'importance':>12}")
    for row in rows[:15]:
        print(f"{row['feature']:<32} {row['importance_mean']:>12.4f}")