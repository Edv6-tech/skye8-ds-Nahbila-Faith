import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


data = Path(__file__).resolve().parents[1] / "data"

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))


agents = pd.read_csv(data / "agents.csv")
services = pd.read_csv(data / "services.csv")
transactions = pd.read_csv(data / "transactions.csv")


# Remove duplicate IDs
agents = agents.drop_duplicates("agent_id")
services = services.drop_duplicates("service_code")
transactions = transactions.drop_duplicates("txn_id")


# Clean dates
agents["registered_on"] = pd.to_datetime(
    agents["registered_on"], errors="coerce", format="mixed"
)


transactions["txn_ts"] = pd.to_datetime(
    transactions["txn_ts"], errors="coerce", format="mixed"
)

invalid_dates = transactions["txn_ts"].isna()
rejected_dates = invalid_dates.sum()

transactions = transactions[~invalid_dates]

# Clean text
agents["agent_type"] = agents["agent_type"].str.strip().str.upper()
agents["status"] = (
    agents["status"]
    .str.strip()
    .str.lower()
    .replace({
        "closed": "inactive",
        "suspended": "inactive",
        "open": "active"
    })
)
services["service_code"] = services["service_code"].str.strip().str.upper()
services["category"] = services["category"].str.strip().str.upper()

transactions["agent_id"] = transactions["agent_id"].str.strip().str.upper()
transactions["service_code"] = transactions["service_code"].str.strip().str.upper()
transactions["status"] = transactions["status"].str.strip().str.upper()


# Convert amounts to numbers
amount_columns = [
    "float_limit_xaf",
    "base_fee_pct",
    "amount_xaf",
    "fee_xaf"
]

for df in [agents, services, transactions]:
    for column in amount_columns:
        if column in df:
            df[column] = pd.to_numeric(
                df[column]
                .astype(str)
                .str.replace(r"[^0-9.-]", "", regex=True),
                errors="coerce"
            )


# Remove transactions with unknown agents
valid_agents = agents["agent_id"]

invalid_transactions = transactions[
    ~transactions["agent_id"].isin(valid_agents)
]

transactions = transactions[
    transactions["agent_id"].isin(valid_agents)
]


# Load data into PostgreSQL
with engine.begin() as connection:

    for _, row in agents.iterrows():
        connection.execute(
            text("""
                INSERT INTO agents (
                    agent_id,
                    agent_name,
                    town,
                    division,
                    registered_on,
                    agent_type,
                    float_limit_xaf,
                    status
                )
                VALUES (
                    :agent_id,
                    :agent_name,
                    :town,
                    :division,
                    :registered_on,
                    :agent_type,
                    :float_limit_xaf,
                    :status
                )
                ON CONFLICT (agent_id) DO NOTHING
            """),
            row.to_dict()
        )

    for _, row in services.iterrows():
        connection.execute(
            text("""
                INSERT INTO services (
                    service_code,
                    service_name,
                    category,
                    base_fee_pct
                )
                VALUES (
                    :service_code,
                    :service_name,
                    :category,
                    :base_fee_pct
                )
                ON CONFLICT (service_code) DO NOTHING
            """),
            row.to_dict()
        )

    for _, row in transactions.iterrows():
        connection.execute(
            text("""
                INSERT INTO transactions (
                    txn_id,
                    agent_id,
                    service_code,
                    txn_ts,
                    amount_xaf,
                    fee_xaf,
                    status,
                    customer_msisdn
                )
                VALUES (
                    :txn_id,
                    :agent_id,
                    :service_code,
                    :txn_ts,
                    :amount_xaf,
                    :fee_xaf,
                    :status,
                    :customer_msisdn
                )
                ON CONFLICT (txn_id) DO NOTHING
            """),
            row.to_dict()
        )


print("Agents:", agents.shape)
print("Services:", services.shape)
print("Transactions:", transactions.shape)
print("Rejected transactions:", len(invalid_transactions))
print("Rejected invalid dates:", rejected_dates)
print("Data loaded successfully.")