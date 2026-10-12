"""Stage C: Model Evaluation and Business Metric Comparison.

Compares Gradient Boosting against the Incumbent heuristic ('Biggest Debt First')
using operational collections metrics:
1. Precision@50 and Precision@100 (capacity constraint of 3 officers).
2. Total Money Recovered (FCFA) at Top 50 and Top 100.
3. Recovery Rate Lift vs Random and vs Biggest-Debt-First.
4. Optimal Expected Value Ranking (P_recovery * Overdue_Amount).
"""
from typing import Dict, List, Any
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, average_precision_score


def precision_at_k(y_true: np.ndarray, ranking_scores: np.ndarray, k: int) -> float:
    """Proportion of accounts in the top-k ranking that actually recover."""
    top_indices = np.argsort(-ranking_scores)[:k]
    return float(np.mean(y_true[top_indices]))


def money_recovered_at_k(
    y_true: np.ndarray,
    overdue_amounts: np.ndarray,
    ranking_scores: np.ndarray,
    k: int
) -> float:
    """Total money successfully recovered from accounts selected in top-k."""
    top_indices = np.argsort(-ranking_scores)[:k]
    recovered_money = overdue_amounts[top_indices] * y_true[top_indices]
    return float(np.sum(recovered_money))


def evaluate_collections_policy(
    df: pd.DataFrame,
    y_true: np.ndarray,
    y_prob: np.ndarray,
    overdue_col: str = "overdue_amount",
    k_list: List[int] = [50, 100, 200, 400]
) -> Dict[str, Any]:
    """Compute complete comparative benchmark between ML Model and Incumbent (Biggest Debt First)."""
    amounts = df[overdue_col].values
    
    # Policy 1: Pure ML Probability (Likelihood to cure)
    ml_prob_scores = y_prob
    
    # Policy 2: Expected Value Policy (P(recovery) * Overdue_Amount)
    # Balances recovery probability against balance size to maximize francs recovered
    ev_scores = y_prob * amounts
    
    # Policy 3: Incumbent Heuristic (Biggest Debt First)
    debt_scores = amounts
    
    # Baseline: Random ordering
    rng = np.random.RandomState(42)
    random_scores = rng.rand(len(y_true))
    
    metrics = {
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "pr_auc": float(average_precision_score(y_true, y_prob)),
        "base_recovery_rate": float(np.mean(y_true)),
        "total_population": len(y_true),
        "total_arrears_book_value": float(np.sum(amounts)),
        "k_evaluations": {}
    }
    
    for k in k_list:
        k_val = min(k, len(y_true))
        
        # Precisions
        p_ev = precision_at_k(y_true, ev_scores, k_val)
        p_prob = precision_at_k(y_true, ml_prob_scores, k_val)
        p_debt = precision_at_k(y_true, debt_scores, k_val)
        p_rand = precision_at_k(y_true, random_scores, k_val)
        
        # Money Recovered in FCFA
        m_ev = money_recovered_at_k(y_true, amounts, ev_scores, k_val)
        m_prob = money_recovered_at_k(y_true, amounts, ml_prob_scores, k_val)
        m_debt = money_recovered_at_k(y_true, amounts, debt_scores, k_val)
        m_rand = money_recovered_at_k(y_true, amounts, random_scores, k_val)
        
        money_lift_fcfa = m_ev - m_debt
        money_lift_pct = (money_lift_fcfa / max(1.0, m_debt)) * 100.0
        
        metrics["k_evaluations"][k_val] = {
            "precision_ev": p_ev,
            "precision_prob": p_prob,
            "precision_incumbent": p_debt,
            "precision_random": p_rand,
            "precision_gain_ratio": p_ev / max(0.001, p_debt),
            "money_recovered_ev": m_ev,
            "money_recovered_prob": m_prob,
            "money_recovered_incumbent": m_debt,
            "money_recovered_random": m_rand,
            "money_lift_fcfa": money_lift_fcfa,
            "money_lift_pct": money_lift_pct
        }
        
    return metrics
