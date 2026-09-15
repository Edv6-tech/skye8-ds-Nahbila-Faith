import pandas as pd
import pytest

from src.clean import (
    clean_numeric_string,
    normalize_boolean_flag,
    normalize_target,
    parse_mixed_dates,
)


def test_parse_mixed_dates_handles_all_three_formats():
    raw = pd.Series(["2025-08-16", "11/10/2025", "08 Apr 2026"])
    parsed = parse_mixed_dates(raw)
    assert parsed.tolist() == [
        pd.Timestamp("2025-08-16"),
        pd.Timestamp("2025-10-11"),  # day-first: 11/10 -> 11 Oct
        pd.Timestamp("2026-04-08"),
    ]


def test_parse_mixed_dates_raises_on_unrecognized_format():
    raw = pd.Series(["2025-08-16", "not-a-date"])
    with pytest.raises(ValueError):
        parse_mixed_dates(raw)


def test_clean_numeric_string_strips_commas():
    raw = pd.Series(["11,358", "8917", "1,234,567"])
    out = clean_numeric_string(raw)
    assert out.tolist() == [11358.0, 8917.0, 1234567.0]


def test_clean_numeric_string_strips_currency_prefix_and_commas():
    raw = pd.Series(["XAF 21260033", "20,483,071", "6012819"])
    out = clean_numeric_string(raw, currency_prefix="XAF")
    assert out.tolist() == [21260033.0, 20483071.0, 6012819.0]


def test_normalize_boolean_flag_handles_all_spellings():
    raw = pd.Series(["TRUE", "FALSE", "yes", "no"])
    out = normalize_boolean_flag(raw)
    assert out.tolist() == [True, False, True, False]


def test_normalize_boolean_flag_rejects_unknown_value():
    raw = pd.Series(["TRUE", "maybe"])
    with pytest.raises(ValueError):
        normalize_boolean_flag(raw)


def test_normalize_target_maps_yes_no_to_1_0():
    raw = pd.Series(["YES", "NO", "YES"])
    out = normalize_target(raw)
    assert out.tolist() == [1, 0, 1]
