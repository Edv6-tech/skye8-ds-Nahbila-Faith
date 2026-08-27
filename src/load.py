import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


# find the data folder (one level up, inside data/)
data_folder = Path(__file__).resolve().parents[1] / "data"

# connect to the database
load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))


# ---------- 1. read the csv files ----------
agents = pd.read_csv(data_folder / "agents.csv")
services = pd.read_csv(data_folder / "services.csv")
transactions = pd.read_csv(data_folder / "transactions.csv")


# ---------- 2. drop duplicate ids ----------
agents = agents.drop_duplicates("agent_id")
services = services.drop_duplicates("service_code")
transactions = transactions.drop_duplicates("txn_id")


# ---------- 3. fix the date columns ----------
# the csv has mixed date formats, so we let pandas figure each one out
# and turn anything it can't understand into NaT (a missing date)
agents["registered_on"] = pd.to_datetime(
    agents["registered_on"], errors="coerce", format="mixed"
)
transactions["txn_ts"] = pd.to_datetime(
    transactions["txn_ts"], errors="coerce", format="mixed"
)

# registered_on is NOT NULL in our schema, so an agent with no valid
# date can't be loaded - we just drop those rows
rejected_agent_dates = agents["registered_on"].isna().sum()
agents = agents[agents["registered_on"].notna()]

rejected_txn_dates = transactions["txn_ts"].isna().sum()
transactions = transactions[transactions["txn_ts"].notna()]


# ---------- 4. clean up text columns ----------
# the csv has extra spaces and mixed UPPER/lower case, so we
# standardise everything the same way
agents["agent_id"] = agents["agent_id"].str.strip().str.upper()
agents["agent_type"] = agents["agent_type"].str.strip().str.upper()

agents["status"] = (
    agents["status"]
    .str.strip()
    .str.lower()
    .replace({
        "closed": "inactive",
        "suspended": "inactive",
        "open": "active",
    })
)

services["service_code"] = services["service_code"].str.strip().str.upper()
services["category"] = services["category"].str.strip().str.upper()

transactions["agent_id"] = transactions["agent_id"].str.strip().str.upper()
transactions["service_code"] = transactions["service_code"].str.strip().str.upper()
transactions["status"] = transactions["status"].str.strip().str.upper()


# ---------- 5. clean up the money columns ----------
# some amounts have commas or a currency symbol in front, e.g. "XAF 1,000"
# so we strip out anything that isn't a digit, a dot, or a minus sign
money_columns = ["float_limit_xaf", "base_fee_pct", "amount_xaf", "fee_xaf"]

for table in [agents, services, transactions]:
    for col in money_columns:
        if col in table.columns:
            table[col] = pd.to_numeric(
                table[col].astype(str).str.replace(r"[^0-9.-]", "", regex=True),
                errors="coerce",
            )


# ---------- 6. drop rows with missing required numbers ----------
rejected_agents = agents["float_limit_xaf"].isna().sum()
agents = agents[agents["float_limit_xaf"].notna()]

rejected_services = services["base_fee_pct"].isna().sum()
services = services[services["base_fee_pct"].notna()]

rejected_amounts = (
    transactions["amount_xaf"].isna() | transactions["fee_xaf"].isna()
).sum()
transactions = transactions[
    transactions["amount_xaf"].notna() & transactions["fee_xaf"].notna()
]


# ---------- 7. keep only transactions with a real agent ----------
# this has to run AFTER we clean the agents table above, so we are
# checking against the agents that will actually make it into the db
known_agent_ids = agents["agent_id"]

rejected_unknown_agents = (~transactions["agent_id"].isin(known_agent_ids)).sum()
transactions = transactions[transactions["agent_id"].isin(known_agent_ids)]


# ---------- 8. keep only transactions with a real service ----------
# same idea as step 7, but for service_code - our schema also has a
# foreign key from transactions.service_code to services.service_code,
# so this has to hold too or the insert will fail
known_service_codes = services["service_code"]

rejected_unknown_services = (
    ~transactions["service_code"].isin(known_service_codes)
).sum()
transactions = transactions[
    transactions["service_code"].isin(known_service_codes)
]


# ---------- 9. protect the customer phone numbers ----------
# customer_msisdn is a personal identifier, so we should not store
# the full number. Instead we keep only the last 4 digits and
# replace the rest with X's, e.g. 6XXXXXXXXX237 -> we still know
# roughly which numbers are repeat customers, but the real number
# is not stored anywhere.
def mask_msisdn(number):
    number = str(number).strip()
    if len(number) <= 4:
        return "X" * len(number)
    return "X" * (len(number) - 4) + number[-4:]

transactions["customer_msisdn"] = transactions["customer_msisdn"].apply(mask_msisdn)


# ---------- 10. turn missing numbers into real NULLs for postgres ----------
for table in [agents, services, transactions]:
    for col in money_columns:
        if col in table.columns:
            table[col] = table[col].astype(object).where(table[col].notna(), None)


# ---------- 11. load the data into postgres, in batches ----------
# inserting one row at a time is slow for 200k+ rows, so instead we
# send a few thousand rows at once. ON CONFLICT DO NOTHING means if
# we run this script twice, rows that are already there get skipped
# instead of duplicated - that is what makes the load idempotent.
def load_table(connection, table_name, id_column, column_names, rows, batch_size=5000):
    if len(rows) == 0:
        return

    columns_sql = ", ".join(column_names)
    values_sql = ", ".join(f":{c}" for c in column_names)

    insert_sql = text(f"""
        INSERT INTO {table_name} ({columns_sql})
        VALUES ({values_sql})
        ON CONFLICT ({id_column}) DO NOTHING
    """)

    for start in range(0, len(rows), batch_size):
        batch = rows[start:start + batch_size]
        connection.execute(insert_sql, batch)


with engine.begin() as connection:

    load_table(
        connection,
        table_name="agents",
        id_column="agent_id",
        column_names=[
            "agent_id", "agent_name", "town", "division",
            "registered_on", "agent_type", "float_limit_xaf", "status",
        ],
        rows=agents.to_dict(orient="records"),
    )

    load_table(
        connection,
        table_name="services",
        id_column="service_code",
        column_names=["service_code", "service_name", "category", "base_fee_pct"],
        rows=services.to_dict(orient="records"),
    )

    load_table(
        connection,
        table_name="transactions",
        id_column="txn_id",
        column_names=[
            "txn_id", "agent_id", "service_code", "txn_ts",
            "amount_xaf", "fee_xaf", "status", "customer_msisdn",
        ],
        rows=transactions.to_dict(orient="records"),
    )


# ---------- 12. print a summary so we can see what happened ----------
print("Agents loaded:", agents.shape[0])
print("Services loaded:", services.shape[0])
print("Transactions loaded:", transactions.shape[0])
print("Transactions rejected:", rejected_txn_dates + rejected_amounts + rejected_unknown_agents + rejected_unknown_services)
print("Rejected transactions (bad date):", rejected_txn_dates)
print("Rejected transactions (missing amount/fee):", rejected_amounts)
print("Rejected transactions (unknown agent):", rejected_unknown_agents)
print("Rejected transactions (unknown service):", rejected_unknown_services)
print("Done.")