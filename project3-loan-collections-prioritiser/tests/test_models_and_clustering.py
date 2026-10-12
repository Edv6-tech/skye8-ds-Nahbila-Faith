"""Unit tests for multi-task modeling, spatial clustering, and bilingual scripts."""
import numpy as np
import pandas as pd
import pytest
from src.features import FEATURE_COLUMNS
from src.model import (
    train_prioritiser,
    train_time_to_cure_regressor,
    train_partial_recovery_regressor,
    predict_recovery_probability,
    predict_time_to_cure,
    predict_partial_recovery_ratio,
    compute_causal_uplift,
    compute_xai_waterfall
)
from src.contact import (
    assign_bamenda_quarter,
    generate_bilingual_scripts,
    calculate_benskin_route_savings,
    apply_action_recommendations
)


@pytest.fixture
def dummy_data():
    np.random.seed(42)
    n = 60
    X = pd.DataFrame(np.random.randn(n, len(FEATURE_COLUMNS)), columns=FEATURE_COLUMNS)
    X["overdue_amount"] = np.random.uniform(10000, 200000, size=n)
    X["prior_payment_ratio"] = np.random.uniform(0.5, 1.2, size=n)
    X["prior_avg_days_late"] = np.random.uniform(0, 20, size=n)
    X["harvest_season"] = np.random.choice([0, 1], size=n)
    X["school_fee_shock"] = np.random.choice([0, 1], size=n)
    X["bureau_total_debt"] = np.random.uniform(0, 400000, size=n)
    X["bureau_active_loans"] = np.random.choice([0, 1, 2], size=n)
    y = pd.Series(np.random.choice([0, 1], size=n, p=[0.7, 0.3]))
    ttc = pd.Series(np.random.randint(3, 28, size=n))
    ratio = pd.Series(np.random.uniform(0.4, 1.0, size=n))
    return X, y, ttc, ratio


def test_model_training_and_inference(dummy_data):
    X, y, ttc, ratio = dummy_data
    # 1. Calibrated Classifier
    clf = train_prioritiser(X, y, calibrate=True)
    probs = predict_recovery_probability(clf, X)
    assert len(probs) == len(X)
    assert np.all((probs >= 0.0) & (probs <= 1.0))

    # 2. Survival Regressor
    reg_ttc = train_time_to_cure_regressor(X, ttc)
    days = predict_time_to_cure(reg_ttc, X)
    assert len(days) == len(X)
    assert np.all((days >= 1) & (days <= 30))

    # 3. Partial Recovery Ratio
    reg_ratio = train_partial_recovery_regressor(X, ratio)
    ratios = predict_partial_recovery_ratio(reg_ratio, X)
    assert len(ratios) == len(X)
    assert np.all((ratios >= 0.35) & (ratios <= 1.00))


def test_causal_uplift_and_segmentation():
    p = np.array([0.85, 0.40, 0.02, 0.15])
    uplift, segments = compute_causal_uplift(p)
    assert len(uplift) == 4
    assert len(segments) == 4
    assert "Self-Curer (SMS Only)" in segments[0]
    assert "Persuadable (High Priority)" in segments[1]
    assert "Lost Cause (Restructure)" in segments[2]


def test_xai_waterfall():
    sample_row = pd.Series({
        "prior_payment_ratio": 0.98,
        "prior_avg_days_late": 1.0,
        "harvest_season": 1,
        "bureau_total_debt": 0.0,
        "bureau_active_loans": 0,
        "overdue_amount": 25000.0,
        "school_fee_shock": 0
    })
    res = compute_xai_waterfall(sample_row)
    assert "top_positive" in res
    assert "top_negative" in res
    assert len(res["top_positive"]) > 0
    assert any("Repayment" in d["factor"] or "Punctual" in d["factor"] for d in res["top_positive"])


def test_bamenda_quarters_and_bilingual_scripts():
    qtr = assign_bamenda_quarter(103380)
    assert any(z in qtr for z in ["Zone 1", "Zone 2", "Zone 3", "Zone 4", "Zone 5"])

    eng, pid = generate_bilingual_scripts(
        account_id=103380,
        loan_id=204551,
        overdue_amount=75000,
        assigned_officer="Officer 2 - Beatrice M.",
        is_vulnerable=False,
        segment="Persuadable"
    )
    assert "Beatrice" in eng
    assert "75,000" in eng
    assert "di salute you" in pid or "Credit Union" in pid


def test_benskin_route_savings():
    df_field = pd.DataFrame({
        "recommended_channel": ["FIELD_VISIT"] * 6,
        "bamenda_quarter": [
            "Commercial Avenue / Food Market (Zone 1)",
            "Commercial Avenue / Food Market (Zone 1)",
            "Nkwen / Mile 2 - Mile 4 (Zone 2)",
            "Nkwen / Mile 2 - Mile 4 (Zone 2)",
            "Mankon / Small Mankon (Zone 4)",
            "Mankon / Small Mankon (Zone 4)"
        ]
    })
    savings = calculate_benskin_route_savings(df_field)
    assert savings["km_saved"] > 0
    assert savings["fuel_cash_saved_fcfa"] > 0
    assert savings["pct_distance_saved"] > 30.0


def test_adaptable_prioritiser(dummy_data):
    X, y, ttc, ratio = dummy_data
    from src.model import AdaptablePrioritiser
    
    clf = train_prioritiser(X, y, calibrate=True)
    engine = AdaptablePrioritiser(clf_model=clf)
    
    # 1. Base prediction
    p_base = engine.predict_adapted_probability(X)
    assert len(p_base) == len(X)
    
    # 2. Branch Archetype Adaptation
    offset = engine.adapt_to_branch("Civil Servant Payroll (Up Station)")
    p_civil = engine.predict_adapted_probability(X)
    assert offset > 0
    assert np.mean(p_civil) > np.mean(p_base)
    
    # 3. Seasonal Adaptation
    engine.adapt_to_season(harvest_boost=0.20, school_fee_drag=0.0)
    p_harvest = engine.predict_adapted_probability(X)
    assert np.mean(p_harvest) > np.mean(p_civil)
    
    # 4. Bayesian Online Feedback Adaptation
    X_acc = X.copy()
    X_acc["SK_ID_CURR"] = np.arange(100, 100 + len(X))
    engine.incorporate_field_feedback(100, "Cured & Settled in Full")
    engine.incorporate_field_feedback(101, "Severe Hardship / Bereavement Shock")
    p_feedback = engine.predict_adapted_probability(X_acc)
    assert p_feedback[0] > p_base[0]
    assert p_feedback[1] < p_base[1]
    
    # 5. Missing Feature Robustness
    X_missing = X.drop(columns=["bureau_total_debt", "pos_cash_max_dpd"], errors="ignore")
    p_missing = engine.predict_adapted_probability(X_missing)
    assert len(p_missing) == len(X_missing)
    assert not np.isnan(p_missing).any()
    
    # 6. Multi-Objective Portfolio Re-ranking
    df_port = X_acc.copy()
    df_port["is_vulnerable"] = False
    df_port.loc[0:5, "is_vulnerable"] = True
    
    ranked_ev = engine.rank_portfolio(df_port, objective="Maximum Cash Flow (EV)")
    assert "rank" in ranked_ev.columns
    assert ranked_ev["expected_gross_recovery_fcfa"].iloc[0] >= ranked_ev["expected_gross_recovery_fcfa"].iloc[-1]
    
    ranked_cures = engine.rank_portfolio(df_port, objective="Maximum Customer Cure Volume")
    assert ranked_cures["recovery_probability"].iloc[0] >= ranked_cures["recovery_probability"].iloc[-1]
    
    ranked_vuln = engine.rank_portfolio(df_port, objective="Vulnerable & Community First")
    assert ranked_vuln["is_vulnerable"].iloc[0] == True


def test_cobac_and_momo_features():
    from src.contact import (
        generate_momo_ussd_strings,
        calculate_cobac_regulatory_savings,
        calculate_small_small_repayment_plan,
        generate_diaspora_sponsor_script
    )
    
    # 1. MoMo USSD Generator
    momo = generate_momo_ussd_strings(75000, 204551)
    assert "*126*9*" in momo["mtn_ussd"]
    assert "*150*1*" in momo["orange_ussd"]
    assert "75000" in momo["mtn_ussd"]
    
    # 2. COBAC Regulatory Capital Savings
    cobac = calculate_cobac_regulatory_savings(150000000.0)
    assert cobac["regulatory_capital_saved_fcfa"] > 0
    assert cobac["capital_preservation_pct"] > 5.0
    assert cobac["par30_risk_reduction_pct"] > 60.0
    
    # 3. Small-Small Micro-repayment Plan
    micro = calculate_small_small_repayment_plan(75000, days_option=30)
    assert micro["daily_payment_fcfa"] == 2500
    assert "2,500 FCFA / day" in micro["plan_text"]
    
    # 4. Diaspora Sponsor Protocol
    diaspora = generate_diaspora_sponsor_script(103380, 204551, 75000, "Officer 1 - John N.")
    assert "Family Guarantor" in diaspora
    assert "75,000 FCFA" in diaspora
    assert "*126*9*" in diaspora


def test_competitive_features():
    from src.contact import (
        generate_momo_push_api_payload,
        generate_voice_ai_ivr_dialog,
        generate_whatsapp_ai_payload,
        generate_njangi_group_resolution,
        generate_cobac_audit_manifest
    )
    
    # 1. MoMo Direct Push API
    momo_push = generate_momo_push_api_payload(50000, 103380, 204551)
    assert momo_push["provider"] == "MTN_MOMO_DIRECT_PUSH"
    assert momo_push["payload"]["amount"] == "50000"
    
    # 2. Voice AI IVR Dialog
    v_ivr = generate_voice_ai_ivr_dialog(103380, 204551, 50000, "Officer 1 - John N.", False)
    assert "dtmf_menu" in v_ivr
    assert "Press 1" in v_ivr["ivr_pidgin_prompt"]
    
    # 3. WhatsApp Business AI Payload
    wa = generate_whatsapp_ai_payload(103380, 204551, 50000, "Hello Pidgin", "*126*9*#")
    assert wa["messaging_product"] == "whatsapp"
    assert "action" in wa["interactive"]
    
    # 4. Njangi Group Network
    nj = generate_njangi_group_resolution(103380, 204551)
    assert "njangi_group_name" in nj
    assert "peer_leverage_protocol" in nj
    
    # 5. COBAC Audit Manifest
    cobac_audit = generate_cobac_audit_manifest(100000000.0)
    assert "cobac_regulation_ref" in cobac_audit
    assert cobac_audit["statutory_capital_preserved_fcfa"] > 0

