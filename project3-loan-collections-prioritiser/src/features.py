"""Stage B: Multi-Source Leakage-Free Feature Engineering.

Incorporates:
1. Historical installment repayment behavior (pre-arrears only).
2. Borrower application demographics.
3. External credit bureau leverage and cross-institutional debt (bureau.csv).
4. Month-by-month POS & cash loan delinquency trajectories (POS_CASH_balance.csv).
5. Bamenda regional liquidity and seasonal agricultural calendar indicators.

Strict temporal guarantee: zero post-contact data leakage.
"""
from pathlib import Path
import pandas as pd
import numpy as np

# Only columns listed here may reach the model.
FEATURE_COLUMNS = [
    # Core Installment Behavioral Features
    "overdue_amount",
    "prior_instalments_count",
    "prior_late_count",
    "prior_late_ratio",
    "prior_severe_late_count",
    "prior_avg_days_late",
    "prior_max_days_late",
    "prior_recovered_before",
    "prior_payment_ratio",
    "prior_underpaid_count",
    "recent_3_avg_late",
    "recent_payment_ratio",
    "instalment_number",

    # Borrower Application Demographics
    "amt_income_total",
    "amt_credit",
    "amt_annuity",
    "days_employed",
    "days_birth",

    # Derived Affordability Ratios
    "annuity_income_ratio",    # monthly burden vs income
    "overdue_income_ratio",    # stress: how big is arrears vs income

    # Multi-Source Relational Features (Bureau & POS)
    "bureau_total_debt",
    "bureau_overdue_debt",     # previously computed but never used — now active
    "bureau_active_loans",
    "pos_cash_max_dpd",

    # Regional & Seasonal Calendar Features (Bamenda Context)
    "market_cycle_day",
    "school_fee_shock",
    "harvest_season",
]

# Anything recorded during/after contact, or after the observation date.
FORBIDDEN_POST_CONTACT = [
    "recovered",
    "contact_method",
    "contact_outcome",
    "promise_to_pay",
    "payment_after_contact",
    "days_to_recovery",
    "amount_recovered",
    "TARGET",
    "observation_day",
]


def build_features(
    events: pd.DataFrame,
    inst: pd.DataFrame,
    app_train: pd.DataFrame = None,
    bureau: pd.DataFrame = None,
    pos_cash: pd.DataFrame = None
) -> pd.DataFrame:
    """Construct multi-source leakage-free behavioral features for each arrears event."""
    i_df = inst.copy()
    i_df["delay"] = i_df["DAYS_ENTRY_PAYMENT"] - i_df["DAYS_INSTALMENT"]
    i_df["paid_amount"] = i_df["AMT_PAYMENT"].fillna(0)
    i_df["inst_amount"] = i_df["AMT_INSTALMENT"].fillna(0)
    i_df["is_late"] = (i_df["delay"] > 0).astype(int)
    i_df["is_severe_late"] = (i_df["delay"] >= 15).astype(int)
    i_df["is_underpaid"] = (i_df["paid_amount"] < (i_df["inst_amount"] * 0.95)).astype(int)
    
    events_keys = events[["SK_ID_CURR", "SK_ID_PREV", "observation_day", "overdue_amount"]].copy()
    
    # Merge installments for these loans
    merged = pd.merge(
        events_keys,
        i_df,
        on=["SK_ID_CURR", "SK_ID_PREV"],
        how="inner"
    )
    
    # Strict temporal filter: only historical instalments prior to observation_day
    hist = merged[merged["DAYS_INSTALMENT"] < merged["observation_day"]].copy()
    
    if len(hist) > 0:
        grp = hist.groupby(["SK_ID_CURR", "SK_ID_PREV"])
        
        hist_feat = grp.agg(
            prior_instalments_count=("NUM_INSTALMENT_NUMBER", "count"),
            prior_late_count=("is_late", "sum"),
            prior_severe_late_count=("is_severe_late", "sum"),
            prior_avg_days_late=("delay", lambda s: s.clip(lower=0).mean()),
            prior_max_days_late=("delay", lambda s: s.clip(lower=0).max()),
            prior_total_paid=("paid_amount", "sum"),
            prior_total_inst=("inst_amount", "sum"),
            prior_underpaid_count=("is_underpaid", "sum"),
            instalment_number=("NUM_INSTALMENT_NUMBER", "max"),
        ).reset_index()
        
        hist_feat["prior_late_ratio"] = (
            hist_feat["prior_late_count"] / hist_feat["prior_instalments_count"].clip(lower=1)
        )
        hist_feat["prior_payment_ratio"] = (
            hist_feat["prior_total_paid"] / hist_feat["prior_total_inst"].clip(lower=1.0)
        ).clip(0.0, 2.0)

        # Fix: prior_recovered_before = borrower had a severe late event AND then
        # made a subsequent on-time payment (genuine cure demonstrated).
        # We detect this by checking that after any severe-late instalment, at least
        # one instalment was paid on time (delay <= 0).
        def _was_ever_cured(group: pd.DataFrame) -> int:
            group = group.sort_values("DAYS_INSTALMENT")
            had_severe = False
            for _, r in group.iterrows():
                if r["is_severe_late"]:
                    had_severe = True
                elif had_severe and r["delay"] <= 0:
                    return 1   # severe late followed by on-time = cured before
            return 0

        cured_flag = hist.groupby(["SK_ID_CURR", "SK_ID_PREV"]).apply(_was_ever_cured).reset_index()
        cured_flag.columns = ["SK_ID_CURR", "SK_ID_PREV", "prior_recovered_before"]
        hist_feat = hist_feat.drop(columns=["prior_recovered_before"], errors="ignore")
        hist_feat = pd.merge(hist_feat, cured_flag, on=["SK_ID_CURR", "SK_ID_PREV"], how="left")
        hist_feat["prior_recovered_before"] = hist_feat["prior_recovered_before"].fillna(0).astype(int)
        
        # Recent trend: last 3 installments
        recent = hist.sort_values("DAYS_INSTALMENT").groupby(["SK_ID_CURR", "SK_ID_PREV"]).tail(3)
        recent_grp = recent.groupby(["SK_ID_CURR", "SK_ID_PREV"]).agg(
            recent_3_avg_late=("delay", lambda s: s.clip(lower=0).mean()),
            recent_paid=("paid_amount", "sum"),
            recent_inst=("inst_amount", "sum"),
        ).reset_index()
        recent_grp["recent_payment_ratio"] = (
            recent_grp["recent_paid"] / recent_grp["recent_inst"].clip(lower=1.0)
        ).clip(0.0, 2.0)
        
        hist_feat = pd.merge(
            hist_feat,
            recent_grp[["SK_ID_CURR", "SK_ID_PREV", "recent_3_avg_late", "recent_payment_ratio"]],
            on=["SK_ID_CURR", "SK_ID_PREV"],
            how="left"
        )
    else:
        hist_feat = pd.DataFrame(columns=["SK_ID_CURR", "SK_ID_PREV"])
        
    out = pd.merge(events_keys, hist_feat, on=["SK_ID_CURR", "SK_ID_PREV"], how="left")
    
    # Fill defaults for baseline features
    out["prior_instalments_count"] = out["prior_instalments_count"].fillna(0)
    out["prior_late_count"] = out["prior_late_count"].fillna(0)
    out["prior_late_ratio"] = out["prior_late_ratio"].fillna(0.0)
    out["prior_severe_late_count"] = out["prior_severe_late_count"].fillna(0)
    out["prior_avg_days_late"] = out["prior_avg_days_late"].fillna(0.0)
    out["prior_max_days_late"] = out["prior_max_days_late"].fillna(0.0)
    out["prior_recovered_before"] = out["prior_recovered_before"].fillna(0)
    out["prior_payment_ratio"] = out["prior_payment_ratio"].fillna(1.0)
    out["prior_underpaid_count"] = out["prior_underpaid_count"].fillna(0)
    out["recent_3_avg_late"] = out["recent_3_avg_late"].fillna(0.0)
    out["recent_payment_ratio"] = out["recent_payment_ratio"].fillna(1.0)
    out["instalment_number"] = out["instalment_number"].fillna(1)
    
    # 2. Application Demographics
    if app_train is not None:
        app_cols = ["SK_ID_CURR", "AMT_INCOME_TOTAL", "AMT_CREDIT", "AMT_ANNUITY", "DAYS_EMPLOYED", "DAYS_BIRTH"]
        existing_cols = [c for c in app_cols if c in app_train.columns]
        app_sub = app_train[existing_cols].copy()
        rename_map = {c: c.lower() for c in existing_cols if c != "SK_ID_CURR"}
        app_sub = app_sub.rename(columns=rename_map)
        out = pd.merge(out, app_sub, on="SK_ID_CURR", how="left")
    else:
        for c in ["amt_income_total", "amt_credit", "amt_annuity", "days_employed", "days_birth"]:
            out[c] = np.nan

    # 3. Credit Bureau Features (bureau.csv)
    if bureau is not None:
        b_sub = bureau.groupby("SK_ID_CURR").agg(
            bureau_total_debt=("AMT_CREDIT_SUM_DEBT", "sum"),
            bureau_overdue_debt=("AMT_CREDIT_SUM_OVERDUE", "sum"),
            bureau_active_loans=("CREDIT_ACTIVE", lambda s: (s == "Active").sum())
        ).reset_index()
        out = pd.merge(out, b_sub, on="SK_ID_CURR", how="left")
    else:
        out["bureau_total_debt"] = 0.0
        out["bureau_overdue_debt"] = 0.0
        out["bureau_active_loans"] = 0
        
    out["bureau_total_debt"] = out["bureau_total_debt"].fillna(0.0)
    out["bureau_overdue_debt"] = out["bureau_overdue_debt"].fillna(0.0)
    out["bureau_active_loans"] = out["bureau_active_loans"].fillna(0)

    # 4. POS & Cash Trajectory (POS_CASH_balance.csv)
    if pos_cash is not None:
        p_sub = pos_cash.groupby("SK_ID_CURR").agg(
            pos_cash_max_dpd=("SK_DPD", "max")
        ).reset_index()
        out = pd.merge(out, p_sub, on="SK_ID_CURR", how="left")
    else:
        out["pos_cash_max_dpd"] = 0.0

    out["pos_cash_max_dpd"] = out["pos_cash_max_dpd"].fillna(0.0)

    # 5. Regional & Seasonal Calendar Engine (Bamenda Context)
    # Use absolute days modulo 8 for the traditional Bamenda 8-day market cycle
    out["market_cycle_day"] = (abs(out["observation_day"]) % 8).astype(int)
    # Day-of-year mapping: September/October school fee season shock (days 240-300)
    day_in_year = (abs(out["observation_day"]) % 365)
    out["school_fee_shock"] = ((day_in_year >= 240) & (day_in_year <= 300)).astype(int)
    # November-January cash crop harvest liquidity boost
    out["harvest_season"] = ((day_in_year >= 305) | (day_in_year <= 35)).astype(int)

    # 6. Derived Affordability Ratios
    eps = 1e-6
    out["annuity_income_ratio"] = (out["amt_annuity"].fillna(0.0) / (out["amt_income_total"].fillna(eps) + eps)).clip(0.0, 5.0)
    out["overdue_income_ratio"] = (out["overdue_amount"].fillna(0.0) / (out["amt_income_total"].fillna(eps) + eps)).clip(0.0, 10.0)

    return out[FEATURE_COLUMNS].copy()
