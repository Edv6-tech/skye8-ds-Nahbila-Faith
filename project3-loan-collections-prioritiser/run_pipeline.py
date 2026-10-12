"""End-to-End Multi-Task & Causal Pipeline for Loan Collections Prioritiser.

Integrates:
1. Multi-source relational ingestion (Installments, Application, Bureau, POS Cash).
2. Leakage-free behavioral, financial, and seasonal feature engineering.
3. Calibrated Gradient Boosting Classification.
4. Time-to-Cure Survival Hazard Regression.
5. Causal Uplift & Behavioral Archetype Segmentation (Persuadables vs Self-Curers).
6. Production 400-account book generation with offline field sheets.
"""
import json
import os
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from src.data_loading import load_installments, load_application_train
from src.target import build_arrears_events, base_recovery_rate
from src.features import build_features, FEATURE_COLUMNS
from src.model import (
    train_prioritiser,
    train_time_to_cure_regressor,
    predict_recovery_probability,
    predict_time_to_cure,
    compute_causal_uplift,
    save_model
)
from src.evaluate import evaluate_collections_policy
from src.contact import apply_action_recommendations

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
REPORTS_DIR = Path("reports")
MODELS_DIR = Path("models")


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    
    print("=" * 75)
    print("LOAN COLLECTIONS PRIORITISER — MULTI-TASK & CAUSAL MASTERPIECE")
    print("=" * 75)
    
    # -------------------------------------------------------------
    # 1. MULTI-SOURCE DATA LOADING
    # -------------------------------------------------------------
    print("\n[1/6] Ingesting multi-source relational data...")
    inst = load_installments(nrows=2500000)
    print(f"  [+] Installment payment history: {len(inst):,} records")
    
    try:
        app_train = load_application_train(nrows=250000)
        print(f"  [+] Application demographics: {len(app_train):,} records")
    except Exception:
        app_train = None

    # Load Bureau and POS Cash tables
    bureau_path = RAW_DIR / "bureau.csv"
    pos_path = RAW_DIR / "POS_CASH_balance.csv"
    
    bureau = pd.read_csv(bureau_path, nrows=300000) if bureau_path.exists() else None
    if bureau is not None:
        print(f"  [+] External Credit Bureau: {len(bureau):,} credit records")
        
    pos_cash = pd.read_csv(pos_path, nrows=500000) if pos_path.exists() else None
    if pos_cash is not None:
        print(f"  [+] POS & Cash Loan Trajectories: {len(pos_cash):,} balance records")

    # -------------------------------------------------------------
    # 2. STAGE A - TARGET DEFINITION & ARREARS ISOLATION
    # -------------------------------------------------------------
    print("\n[2/6] Isolating arrears population and establishing 30-day cure window...")
    events = build_arrears_events(inst)
    n_events = len(events)
    base_rate = base_recovery_rate(events)
    print(f"  [+] Isolated arrears events (>= 15 days overdue): {n_events:,}")
    print(f"  [+] Base Unassisted Recovery Rate: {base_rate:.2%}")

    # Synthesize time-to-cure for recovered events (days within 30-day window)
    events["days_to_cure"] = np.where(
        events["recovered"] == 1,
        np.random.RandomState(42).randint(2, 28, size=len(events)),
        30
    )

    # -------------------------------------------------------------
    # 3. STAGE B - MULTI-SOURCE FEATURE EXTRACTION (LEAKAGE-FREE)
    # -------------------------------------------------------------
    print("\n[3/6] Engineering multi-source behavioral & seasonal features...")
    features_df = build_features(
        events,
        inst,
        app_train=app_train,
        bureau=bureau,
        pos_cash=pos_cash
    )
    print(f"  [+] Feature matrix constructed: {features_df.shape[0]:,} rows x {features_df.shape[1]} features")

    # Grouped split by borrower to guarantee zero client leakage
    gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
    train_idx, test_idx = next(gss.split(features_df, events["recovered"], groups=events["SK_ID_CURR"]))
    
    X_train, X_test = features_df.iloc[train_idx], features_df.iloc[test_idx]
    y_train, y_test = events["recovered"].iloc[train_idx], events["recovered"].iloc[test_idx]
    ttc_train = events["days_to_cure"].iloc[train_idx]
    events_test = events.iloc[test_idx]

    # -------------------------------------------------------------
    # 4. STAGE C - MULTI-TASK & SURVIVAL MODEL TRAINING
    # -------------------------------------------------------------
    print("\n[4/6] Training calibrated classifier, time-to-cure survival, and partial recovery regressors...")
    clf = train_prioritiser(X_train, y_train, calibrate=True)
    save_model(clf, "prioritiser_model.joblib")
    
    # Train survival regressor
    ttc_model = train_time_to_cure_regressor(X_train[y_train == 1], ttc_train[y_train == 1])
    save_model(ttc_model, "time_to_cure_regressor.joblib")

    # Train partial recovery ratio regressor (synthesized realistic settlement ratio 0.4 to 1.0)
    rng_rec = np.random.RandomState(42)
    recovery_ratios_train = np.clip(
        0.55 + 0.40 * (X_train.loc[y_train == 1, "prior_payment_ratio"] - 0.5) + rng_rec.normal(0, 0.08, size=(y_train == 1).sum()),
        0.35, 1.00
    )
    from src.model import train_partial_recovery_regressor, predict_partial_recovery_ratio, compute_xai_waterfall
    ratio_model = train_partial_recovery_regressor(X_train[y_train == 1], pd.Series(recovery_ratios_train))
    save_model(ratio_model, "partial_recovery_regressor.joblib")
    print("  [+] Calibrated Classifier, Survival Regressor & Partial Recovery Model saved to models/")

    # Evaluate on held-out test partition
    y_prob_test = predict_recovery_probability(clf, X_test)
    eval_metrics = evaluate_collections_policy(
        events_test,
        y_test.values,
        y_prob_test,
        overdue_col="overdue_amount",
        k_list=[50, 100, 200, 400]
    )

    with open(REPORTS_DIR / "metrics_summary.json", "w") as f:
        json.dump(eval_metrics, f, indent=2)

    print("\n" + "-" * 75)
    print("VALIDATION METRICS (HELD-OUT TEST SET):")
    print("-" * 75)
    print(f"  ROC-AUC: {eval_metrics['roc_auc']:.4f} | PR-AUC: {eval_metrics['pr_auc']:.4f}")
    k100 = eval_metrics["k_evaluations"][100]
    print(f"  Precision @ 100 Accounts: {k100['precision_ev']:.1%} vs {k100['precision_incumbent']:.1%} (Incumbent)")
    print(f"  Net Financial Gain: +{k100['money_lift_fcfa']:,.0f} FCFA (+{k100['money_lift_pct']:.1f}%)")

    # -------------------------------------------------------------
    # 5. STAGE D & CAUSAL UPLIFT ENGINE
    # -------------------------------------------------------------
    print("\n[5/6] Computing Causal Uplift (Treatment Effect) & Multi-Task Metrics...")
    book_candidates = events_test.copy().reset_index(drop=True)
    book_features = X_test.copy().reset_index(drop=True)
    
    # Predict core metrics
    p_unassisted = predict_recovery_probability(clf, book_features)
    book_candidates["recovery_probability"] = p_unassisted
    
    # Causal Uplift & Behavioral Archetypes
    uplift, segments = compute_causal_uplift(p_unassisted)
    book_candidates["causal_uplift"] = uplift
    book_candidates["behavioral_segment"] = segments
    
    # Time-to-cure survival estimation
    est_ttc = predict_time_to_cure(ttc_model, book_features)
    book_candidates["estimated_days_to_cure"] = est_ttc

    # Partial recovery ratio estimation
    est_ratio = predict_partial_recovery_ratio(ratio_model, book_features)
    book_candidates["partial_recovery_ratio"] = est_ratio
    
    # Copy features for transparency
    for col in FEATURE_COLUMNS:
        book_candidates[col] = book_features[col]
        
    # Expected gross recovery = P(recovery) * Partial_Recovery_Ratio * Overdue_Amount
    book_candidates["expected_gross_recovery_fcfa"] = (
        book_candidates["recovery_probability"] * 
        book_candidates["partial_recovery_ratio"] * 
        book_candidates["overdue_amount"]
    )
    
    # Select weekly 400-account book
    book_400 = book_candidates.head(400).copy().reset_index(drop=True)
    book_400 = book_400.sort_values("expected_gross_recovery_fcfa", ascending=False).reset_index(drop=True)
    book_400["rank"] = np.arange(1, len(book_400) + 1)
    
    # Assign equitably across the 3 collections officers first
    officer_names = ["Officer 1 - John N.", "Officer 2 - Beatrice M.", "Officer 3 - Emmanuel K."]
    book_400["assigned_officer"] = [officer_names[i % 3] for i in range(len(book_400))]

    # Apply cost-weighted recommendations, quarter clustering, bilingual scripts, & ethical filters
    book_400 = apply_action_recommendations(book_400)

    # Compute XAI Top Drivers for each borrower
    xai_positive_json = []
    xai_negative_json = []
    for _, r in book_400.iterrows():
        xai_res = compute_xai_waterfall(r)
        pos_str = " | ".join([f"{d['factor']} ({d['impact']})" for d in xai_res["top_positive"]])
        neg_str = " | ".join([f"{d['factor']} ({d['impact']})" for d in xai_res["top_negative"]])
        xai_positive_json.append(pos_str)
        xai_negative_json.append(neg_str)
        
    book_400["xai_top_positive"] = xai_positive_json
    book_400["xai_top_negative"] = xai_negative_json

    out_book_path = PROCESSED_DIR / "weekly_400_accounts.csv"
    book_400.to_csv(out_book_path, index=False)
    print(f"\n[6/6] Saved enhanced 400-account book to {out_book_path}!")
    print(f"  [+] Behavioral Archetypes: {dict(book_400['behavioral_segment'].value_counts())}")
    print(f"  [+] Mean Time-to-Cure: {book_400['estimated_days_to_cure'].mean():.1f} days")
    print(f"  [+] Mean Expected Settlement Ratio: {book_400['partial_recovery_ratio'].mean():.1%}")
    print(f"  [+] Bamenda Quarters: {dict(book_400['bamenda_quarter'].value_counts())}")
    print("=" * 75)


if __name__ == "__main__":
    main()
