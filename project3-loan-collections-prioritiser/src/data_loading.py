from pathlib import Path
import pandas as pd

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


def load_installments(nrows=None) -> pd.DataFrame:
    """Home Credit instalment payment history."""
    return pd.read_csv(RAW / "installments_payments.csv", nrows=nrows)


def load_previous_application(nrows=None) -> pd.DataFrame:
    return pd.read_csv(RAW / "previous_application.csv", nrows=nrows)


def load_application_train(nrows=None) -> pd.DataFrame:
    return pd.read_csv(RAW / "application_train.csv", nrows=nrows)


def load_lending_club(nrows=None, usecols=None) -> pd.DataFrame:
    """LendingClub loan data containing full repayment histories, late payments, and recoveries."""
    path = RAW / "accepted_2007_to_2018Q4.csv"
    if not path.exists():
        raise FileNotFoundError(f"LendingClub dataset not found at {path}")
    return pd.read_csv(path, nrows=nrows, usecols=usecols, low_memory=False)

