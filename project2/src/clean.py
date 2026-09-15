"""
Cleans the four raw files: containers.csv, brokers.csv, importers.csv,
vessels.csv.

Run with:
    python -m src.clean
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def parse_mixed_dates(series: pd.Series) -> pd.Series:
    """arrived_on has 3 different date formats mixed together:
    2025-08-16, 11/10/2025, and 08 Apr 2026.

    The slash one is day first, not month first - I checked, there are
    values like 29/11/2025 where the first number is > 12, so it can't
    be MM/DD/YYYY.

    Tries each format one at a time and fills in whatever matches. If
    anything is left over at the end it raises, instead of quietly
    turning into NaT.
    """
    s = series.astype(str).str.strip()
    parsed = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")

    formats = ["%Y-%m-%d", "%d/%m/%Y", "%d %b %Y"]
    remaining = s.copy()
    for fmt in formats:
        mask = parsed.isna() & remaining.notna()
        attempt = pd.to_datetime(remaining[mask], format=fmt, errors="coerce")
        parsed.loc[attempt.index] = parsed.loc[attempt.index].fillna(attempt)

    unparsed = parsed.isna().sum()
    if unparsed:
        raise ValueError(
            f"{unparsed} arrived_on values didn't match any of the 3 "
            "formats I know about. Go check data/raw/containers.csv."
        )
    return parsed


def clean_numeric_string(series: pd.Series, currency_prefix: str | None = None) -> pd.Series:
    """Strips commas and an optional currency prefix, then converts to
    a number.

    gross_weight_kg sometimes has commas ("11,358").
    declared_value_xaf sometimes has commas AND an "XAF " prefix
    ("XAF 21260033").
    """
    s = series.astype(str).str.strip()
    if currency_prefix:
        s = s.str.replace(currency_prefix, "", regex=False).str.strip()
    s = s.str.replace(",", "", regex=False)
    out = pd.to_numeric(s, errors="coerce")
    if out.isna().any():
        bad = series[out.isna()].unique()[:10]
        raise ValueError(f"Couldn't parse these as numbers: {bad}")
    return out


def normalize_boolean_flag(series: pd.Series) -> pd.Series:
    """inspection_selected shows up as TRUE/FALSE/yes/no - same
    meaning, 4 different spellings. Map them all to real booleans.
    """
    mapping = {"true": True, "false": False, "yes": True, "no": False}
    normalized = series.astype(str).str.strip().str.lower().map(mapping)
    if normalized.isna().any():
        bad = series[normalized.isna()].unique()[:10]
        raise ValueError(f"Unrecognized inspection_selected values: {bad}")
    return normalized


def normalize_target(series: pd.Series) -> pd.Series:
    """delayed is YES/NO as text, turn it into 1/0."""
    mapping = {"YES": 1, "NO": 0}
    out = series.astype(str).str.strip().map(mapping)
    if out.isna().any():
        raise ValueError("Unrecognized values in 'delayed' column.")
    return out.astype(int)


# --------------------------------------------------------------------------
# loaders for each file
# --------------------------------------------------------------------------


def load_containers(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str)
    n_raw = len(df)

    # Found 300 fully duplicated rows (150 container_ids showing up
    # twice, every column identical). Just drop the second copy, keep
    # the first - these aren't conflicting records, they're exact
    # copies of each other.
    n_dup = df["container_id"].duplicated().sum()
    df = df.drop_duplicates(subset="container_id", keep="first")
    logger.info("containers: dropped %d duplicate container_id rows", n_dup)

    df["arrived_on"] = parse_mixed_dates(df["arrived_on"])

    df["gross_weight_kg"] = clean_numeric_string(df["gross_weight_kg"])
    df["declared_value_xaf"] = clean_numeric_string(
        df["declared_value_xaf"], currency_prefix="XAF"
    )

    df["inspection_selected"] = normalize_boolean_flag(df["inspection_selected"])
    df["delayed"] = normalize_target(df["delayed"])

    # These read in as strings because of the mixed dtypes elsewhere
    # in the file, but they're actually fine ints once cast.
    df["hs_chapter"] = df["hs_chapter"].astype(int)
    df["days_to_clear"] = df["days_to_clear"].astype(int)

    # 220 rows point to a vessel_id that isn't in vessels.csv at all.
    # Keeping these rows (the label doesn't depend on the vessel
    # table), but flagging them so any vessel-based feature later
    # knows to expect a missing join instead of crashing on it.
    logger.info(
        "containers: %d rows after cleaning (started with %d)",
        len(df),
        n_raw,
    )
    return df.reset_index(drop=True)


def load_brokers(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str)
    df["licence_year"] = df["licence_year"].astype(int)
    df["staff"] = df["staff"].astype(int)
    return df


def load_importers(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str)
    df["registered_year"] = df["registered_year"].astype(int)
    return df


def load_vessels(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str)
    df["arrived_on"] = parse_mixed_dates(df["arrived_on"])
    df["teu_discharged"] = df["teu_discharged"].astype(int)
    return df


def flag_orphan_vessels(containers: pd.DataFrame, vessels: pd.DataFrame) -> pd.DataFrame:
    """Marks containers whose vessel_id doesn't exist in vessels.csv,
    so vessel features later don't fail silently on a missing join.
    """
    known = set(vessels["vessel_id"])
    containers = containers.copy()
    containers["vessel_missing"] = ~containers["vessel_id"].isin(known)
    n_orphan = containers["vessel_missing"].sum()
    logger.info(
        "containers: %d rows (%d unique vessel_ids) reference a vessel "
        "not in vessels.csv; flagged with vessel_missing",
        n_orphan,
        containers.loc[containers["vessel_missing"], "vessel_id"].nunique(),
    )
    return containers


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    containers = load_containers(RAW_DIR / "containers.csv")
    brokers = load_brokers(RAW_DIR / "brokers.csv")
    importers = load_importers(RAW_DIR / "importers.csv")
    vessels = load_vessels(RAW_DIR / "vessels.csv")

    containers = flag_orphan_vessels(containers, vessels)

    containers.to_csv(PROCESSED_DIR / "containers.csv", index=False)
    brokers.to_csv(PROCESSED_DIR / "brokers.csv", index=False)
    importers.to_csv(PROCESSED_DIR / "importers.csv", index=False)
    vessels.to_csv(PROCESSED_DIR / "vessels.csv", index=False)

    logger.info("Cleaned files written to %s", PROCESSED_DIR)


if __name__ == "__main__":
    main()
