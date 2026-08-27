import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text



data_folder = Path(__file__).resolve().parents[1] / "data"


load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))



agents = pd.read_csv(data_folder / "agents.csv")
services = pd.read_csv(data_folder / "services.csv")
transactions = pd.read_csv(data_folder / "transactions.csv")

agents = agents.drop_duplicates("agent_id")
services = services.drop_duplicates("service_code")
transactions = transactions.drop_duplicates("txn_id")


# fix dates
agents["registered_on"] = pd.to_datetime(
    agents["registered_on"], errors="coerce", format="mixed"
)
transactions["txn_ts"] = pd.to_datetime(
    transactions["txn_ts"], errors="coerce", format="mixed"
)

# drop bad dates
rejected_agent_dates = agents["registered_on"].isna().sum()
agents = agents[agents["registered_on"].notna()]

rejected_txn_dates = transactions["txn_ts"].isna().sum()
transactions = transactions[transactions["txn_ts"].notna()]


# clean text cols
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


# clean money cols
money_columns = ["float_limit_xaf", "base_fee_pct", "amount_xaf", "fee_xaf"]

for table in [agents, services, transactions]:
    for col in money_columns:
        if col in table.columns:
            table[col] = pd.to_numeric(
                table[col].astype(str).str.replace(r"[^0-9.-]", "", regex=True),
                errors="coerce",
            )


# drop rows missing required numbers
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


# drop transactions with unknown agent
known_agent_ids = agents["agent_id"]

rejected_unknown_agents = (~transactions["agent_id"].isin(known_agent_ids)).sum()
transactions = transactions[transactions["agent_id"].isin(known_agent_ids)]


# drop transactions with unknown service
known_service_codes = services["service_code"]

rejected_unknown_services = (
    ~transactions["service_code"].isin(known_service_codes)
).sum()
transactions = transactions[
    transactions["service_code"].isin(known_service_codes)
]


# mask customer numbers
def mask_msisdn(number):
    number = str(number).strip()
    if len(number) <= 4:
        return "X" * len(number)
    return "X" * (len(number) - 4) + number[-4:]

transactions["customer_msisdn"] = transactions["customer_msisdn"].apply(mask_msisdn)


# nan to none for postgres
for table in [agents, services, transactions]:
    for col in money_columns:
        if col in table.columns:
            table[col] = table[col].astype(object).where(table[col].notna(), None)


# batch insert function
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


# summary
print("Agents loaded:", agents.shape[0])
print("Services loaded:", services.shape[0])
print("Transactions loaded:", transactions.shape[0])
print("Transactions rejected:", rejected_txn_dates + rejected_amounts + rejected_unknown_agents + rejected_unknown_services)
print("Rejected transactions (bad date):", rejected_txn_dates)
print("Rejected transactions (missing amount/fee):", rejected_amounts)
print("Rejected transactions (unknown agent):", rejected_unknown_agents)
print("Rejected transactions (unknown service):", rejected_unknown_services)
print("Done.")