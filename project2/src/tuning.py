
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import optuna
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline import build_pipeline
from split import cv_splits, time_split

TARGET = "delayed"
SEARCH_ENCODING = "target"
SEARCH_N_SPLITS = 3
N_TRIALS = 80
STUDY_NAME = "skye8_pr3_gbm"
STORAGE = "sqlite:///artifacts/optuna_study.db"


def objective(trial: optuna.Trial, train_cv: pd.DataFrame) -> float:
    params = {
        "max_iter": trial.suggest_int("max_iter", 50, 300),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "max_leaf_nodes": trial.suggest_int("max_leaf_nodes", 15, 127),
        "l2_regularization": trial.suggest_float("l2_regularization", 0.0, 5.0),
        "max_depth": trial.suggest_int("max_depth", 3, 12),
        "min_samples_leaf": trial.suggest_int("min_samples_leaf", 5, 100),
    }
    model = HistGradientBoostingClassifier(random_state=42, **params)

    scores = []
    for train_idx, val_idx in cv_splits(train_cv, n_splits=SEARCH_N_SPLITS):
        train_fold, val_fold = train_cv.iloc[train_idx], train_cv.iloc[val_idx]
        pipe = build_pipeline(SEARCH_ENCODING, model=model)
        pipe.fit(train_fold, train_fold[TARGET])
        prob = pipe.predict_proba(val_fold)[:, 1]
        scores.append(roc_auc_score(val_fold[TARGET], prob))
    return float(np.mean(scores))


def run(processed_path: str = "data/processed/containers.csv") -> dict:
    df = pd.read_csv(processed_path, parse_dates=["arrived_on"])
    train_cv, held_out = time_split(df)

    Path("artifacts").mkdir(exist_ok=True)
    study = optuna.create_study(
        study_name=STUDY_NAME,
        storage=STORAGE,
        direction="maximize",
        load_if_exists=True,
    )

    trial_times = []

    def timing_callback(study, trial):
        trial_times.append(trial.duration.total_seconds())

    remaining = N_TRIALS - len(study.trials)
    if remaining > 0:
        study.optimize(
            lambda trial: objective(trial, train_cv),
            n_trials=remaining,
            callbacks=[timing_callback],
        )

    trial_rows = []
    running_best = -np.inf
    for t in study.trials:
        if t.value is not None and t.value > running_best:
            running_best = t.value
        trial_rows.append({"number": t.number, "value": t.value, "best_so_far": running_best})

    total_seconds = sum(t.duration.total_seconds() for t in study.trials if t.duration is not None)

    n = len(trial_rows)
    if n >= 20:
        best_before_final_20 = trial_rows[n - 20]["best_so_far"]
    else:
        best_before_final_20 = trial_rows[0]["best_so_far"]
    best_after_all = trial_rows[-1]["best_so_far"]
    marginal_gain_final_20 = best_after_all - best_before_final_20

    summary = {
        "n_trials": n,
        "best_value": study.best_value,
        "best_params": study.best_params,
        "total_compute_seconds": round(total_seconds, 1),
        "marginal_gain_final_20_trials": round(marginal_gain_final_20, 5),
        "search_encoding": SEARCH_ENCODING,
        "search_n_splits": SEARCH_N_SPLITS,
    }

    with open("artifacts/stage_d_tuning_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    with open("artifacts/stage_d_trial_history.json", "w") as f:
        json.dump(trial_rows, f, indent=2)

    return summary, trial_rows


def plot_best_score(trial_rows: list, out_path: str = "artifacts/optuna_best_score_plot.png"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    numbers = [r["number"] for r in trial_rows]
    best = [r["best_so_far"] for r in trial_rows]

    plt.figure(figsize=(8, 5))
    plt.plot(numbers, best)
    plt.xlabel("trial number")
    plt.ylabel("best ROC AUC so far")
    plt.title("Optuna search, best score by trial")
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


if __name__ == "__main__":
    summary, trial_rows = run()
    print(json.dumps(summary, indent=2))
    plot_best_score(trial_rows)
    print("plot saved to artifacts/optuna_best_score_plot.png")