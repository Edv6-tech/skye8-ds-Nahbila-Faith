"""Stage A: define arrears events and the recovery label.

DEFINITIONS AND DEFENSE:
1. Arrears Event:
   An instalment is more than ARREARS_DAYS (15 days) past due and not yet paid
   in full on the observation date.
   Defense:
   In Central African microfinance (CEMAC / COBAC regulation and Bamenda credit unions),
   days 1 to 14 represent grace/operational delays (salary cycles, market days).
   At day 15, the loan formally moves from standard monitoring to PAR-15 (Portfolio at Risk)
   and requires active collections officer intervention.

2. Observation Date:
   observation_day = DAYS_INSTALMENT + ARREARS_DAYS (i.e. due date + 15 days).
   This is the exact day the account lands on the collections officer's desk.

3. Recovery:
   The overdue instalment is paid in full (>= 95% of AMT_INSTALMENT) within
   RECOVERY_WINDOW (30 days) following the observation date (i.e. paid within 45 days
   of the original due date).
   Defense:
   A 30-day recovery window aligns with the monthly loan cycle. If an account in arrears
   settles before the next billing cycle, it cures without entering non-performing
   loan (NPL / PAR-60) status.

4. Population:
   Strictly accounts that have entered arrears (delay >= 15 days or underpaid).
   Training on all borrowers would model credit scoring/default origination, which is
   the wrong distribution for delinquent account recovery.
"""
import pandas as pd
import numpy as np

ARREARS_DAYS = 15
RECOVERY_WINDOW = 30


def build_arrears_events(inst: pd.DataFrame) -> pd.DataFrame:
    """Return one row per arrears event with columns:
    SK_ID_CURR, SK_ID_PREV, observation_day, overdue_amount, recovered (0/1).
    """
    df = inst.copy()
    
    # Calculate payment delay relative to due date (positive = late)
    # If DAYS_ENTRY_PAYMENT is NaN, the payment was never recorded
    df["days_late"] = df["DAYS_ENTRY_PAYMENT"] - df["DAYS_INSTALMENT"]
    
    # Calculate payment compliance
    amt_paid = df["AMT_PAYMENT"].fillna(0)
    amt_inst = df["AMT_INSTALMENT"].fillna(0)
    df["underpaid"] = amt_paid < (amt_inst * 0.95)
    
    # An arrears event occurs if payment was delayed >= ARREARS_DAYS
    # or was unpaid/underpaid past the 15-day mark
    is_arrears = (
        (df["days_late"] >= ARREARS_DAYS) |
        (df["days_late"].isna()) |
        (df["underpaid"] & (df["days_late"] >= 0))
    ) & (amt_inst > 0)
    
    events = df[is_arrears].copy()
    
    # Set observation day: when the account hits 15 days overdue
    events["observation_day"] = events["DAYS_INSTALMENT"] + ARREARS_DAYS
    events["overdue_amount"] = events["AMT_INSTALMENT"]
    
    # Recovery definition:
    # Paid in full (>= 95% of AMT_INSTALMENT) within RECOVERY_WINDOW days after observation_day
    # (equivalent to days_late <= ARREARS_DAYS + RECOVERY_WINDOW and not underpaid)
    paid_in_window = (
        (events["days_late"] <= (ARREARS_DAYS + RECOVERY_WINDOW)) &
        (~events["underpaid"])
    )
    events["recovered"] = paid_in_window.astype(int)
    
    # Deduplicate to one event per client-loan at observation
    # Taking the most recent observation day for each active arrears event
    events = events.sort_values("observation_day").groupby(
        ["SK_ID_CURR", "SK_ID_PREV"], as_index=False
    ).last()
    
    result_cols = [
        "SK_ID_CURR",
        "SK_ID_PREV",
        "observation_day",
        "overdue_amount",
        "recovered"
    ]
    return events[result_cols].reset_index(drop=True)


def base_recovery_rate(events: pd.DataFrame) -> float:
    """Share of arrears events that recover with no intervention."""
    if len(events) == 0:
        return 0.0
    return float(events["recovered"].mean())


def build_lending_club_arrears_events(df: pd.DataFrame) -> pd.DataFrame:
    """Isolate LendingClub arrears population and compute recovery label and overdue amount.
    
    Arrears population: loans marked 'Charged Off', 'Default', 'Late (31-120 days)', or 'Late (16-30 days)'.
    Recovery label: 1 if borrower paid post-delinquency recoveries > 0 or cured, 0 otherwise.
    """
    arrears_statuses = ['Charged Off', 'Default', 'Late (31-120 days)', 'Late (16-30 days)']
    events = df[df['loan_status'].isin(arrears_statuses)].copy()
    
    # Overdue amount: unpaid principal balance at delinquency
    if 'total_rec_prncp' in events.columns and 'loan_amnt' in events.columns:
        unpaid = events['loan_amnt'] - events['total_rec_prncp'].fillna(0)
        events['overdue_amount'] = np.maximum(unpaid, events['installment'].fillna(100.0))
    else:
        events['overdue_amount'] = events['loan_amnt']

    # Recovery definition: actual recovery of funds post-delinquency
    recoveries_col = events['recoveries'].fillna(0) if 'recoveries' in events.columns else pd.Series(0, index=events.index)
    events['recovery_amount'] = recoveries_col
    events['recovered'] = ((recoveries_col > 0) | (events['loan_status'] == 'Late (16-30 days)')).astype(int)

    # Identifiers for pipeline compatibility
    events['SK_ID_CURR'] = events['id'].astype(str)
    events['SK_ID_PREV'] = events['id'].astype(str)
    events['observation_day'] = 0

    return events.reset_index(drop=True)

