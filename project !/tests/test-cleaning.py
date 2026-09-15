import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import cleaning


def test_clean_text_strips_and_uppercases():
    series = pd.Series([" a001 ", "a002", " A003"])
    result = cleaning.clean_text(series)
    assert list(result) == ["A001", "A002", "A003"]


def test_clean_status_replaces_known_values():
    series = pd.Series(["Closed", "SUSPENDED", "open", "active"])
    replacements = {"closed": "inactive", "suspended": "inactive", "open": "active"}
    result = cleaning.clean_status(series, replacements)
    assert list(result) == ["inactive", "inactive", "active", "active"]


def test_clean_money_strips_currency_symbols():
    series = pd.Series(["XAF 1,000", "500", "2,500.50"])
    result = cleaning.clean_money(series)
    assert list(result) == [1000.0, 500.0, 2500.50]


def test_clean_money_invalid_becomes_nan():
    series = pd.Series(["abc", "", "100"])
    result = cleaning.clean_money(series)
    assert result.isna().sum() == 2
    assert result.iloc[2] == 100.0


def test_parse_dates_handles_mixed_formats():
    series = pd.Series(["2025-01-15", "15/01/2025"])
    result = cleaning.parse_dates(series)
    assert result.notna().all()


def test_parse_dates_invalid_becomes_nat():
    series = pd.Series(["2025-01-15", "not a date"])
    result = cleaning.parse_dates(series)
    assert result.isna().sum() == 1


def test_drop_missing_removes_null_rows():
    df = pd.DataFrame({"a": [1, None, 3]})
    result, rejected = cleaning.drop_missing(df, "a")
    assert len(result) == 2
    assert rejected == 1


def test_drop_missing_any_removes_rows_missing_either_column():
    df = pd.DataFrame({"a": [1, None, 3], "b": [1, 2, None]})
    result, rejected = cleaning.drop_missing_any(df, ["a", "b"])
    assert len(result) == 1
    assert rejected == 2


def test_filter_known_values_keeps_only_matches():
    df = pd.DataFrame({"agent_id": ["A1", "A2", "A3"]})
    known = pd.Series(["A1", "A3"])
    result, rejected = cleaning.filter_known_values(df, "agent_id", known)
    assert list(result["agent_id"]) == ["A1", "A3"]
    assert rejected == 1


def test_mask_msisdn_keeps_last_4_digits():
    assert cleaning.mask_msisdn("670123456") == "XXXXX3456"


def test_mask_msisdn_short_number_all_masked():
    assert cleaning.mask_msisdn("12") == "XX"


def test_nulls_to_none_converts_nan_to_none():
    df = pd.DataFrame({"amount": [1.0, None, 3.0]})
    result = cleaning.nulls_to_none(df, ["amount"])
    assert result["amount"].iloc[1] is None


def test_load_table_is_idempotent():
    # in-memory sqlite db just for this test, no real postgres needed
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE agents (
                agent_id TEXT PRIMARY KEY,
                agent_name TEXT
            )
        """))

        rows = [{"agent_id": "A1", "agent_name": "Test Agent"}]

        # run the same load twice
        cleaning.load_table(connection, "agents", "agent_id", ["agent_id", "agent_name"], rows)
        cleaning.load_table(connection, "agents", "agent_id", ["agent_id", "agent_name"], rows)

        count = connection.execute(text("SELECT COUNT(*) FROM agents")).scalar()
        assert count == 1