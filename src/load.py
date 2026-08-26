import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


# get the data folder
data = Path(__file__).resolve().parents[1] / "data"

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))


# read the csv files
agents = pd.read_csv(data / "agents.csv")
services = pd.read_csv(data / "services.csv")
transactions = pd.read_csv(data / "transactions.csv")


# remove duplicate ids
agents = agents.drop_duplicates("agent_id")
services = services.drop_duplicates("service_code")
transactions = transactions.drop_duplicates("txn_id")


# clean the dates
agents["registered_on"] = pd.to_datetime(
    agents["registered_on"],
    errors="coerce",
    format="mixed"
)

transactions["txn_ts"] = pd.to_datetime(
    transactions["txn_ts"],
    errors="coerce",
    format="mixed"
)


# remove transactions with bad dates
invalid_dates = transactions["txn_ts"].isna()
rejected_dates = invalid_dates.sum()

transactions = transactions[~invalid_dates]


# clean the text values
agents["agent_id"] = agents["agent_id"].str.strip().str.upper()

agents["agent_type"] = (
    agents["agent_type"]
    .str.strip()
    .str.upper()
)

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

services["service_code"] = (
    services["service_code"]
    .str.strip()
    .str.upper()
)

services["category"] = (
    services["category"]
    .str.strip()
    .str.upper()
)

transactions["agent_id"] = (
    transactions["agent_id"]
    .str.strip()
    .str.upper()
)

transactions["service_code"] = (
    transactions["service_code"]
    .str.strip()
    .str.upper()
)

transactions["status"] = (
    transactions["status"]
    .str.strip()
    .str.upper()
)


# convert the amounts to numbers
amount_columns = [
    "float_limit_xaf",
    "base_fee_pct",
    "amount_xaf",
    "fee_xaf"
]

for df in [agents, services, transactions]:
    for column in amount_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(
                df[column]
                .astype(str)
                .str.replace(r"[^0-9.-]", "", regex=True),
                errors="coerce"
            )


# remove agents where the float limit is missing
invalid_agents = agents[
    agents["float_limit_xaf"].isna()
]

rejected_agents = len(invalid_agents)

agents = agents[
    agents["float_limit_xaf"].notna()
]


# remove services where the base fee is missing
invalid_services = services[
    services["base_fee_pct"].isna()
]

rejected_services = len(invalid_services)

services = services[
    services["base_fee_pct"].notna()
]


# remove transactions where amount or fee is missing
invalid_transaction_amounts = transactions[
    transactions["amount_xaf"].isna()
    | transactions["fee_xaf"].isna()
]

rejected_amounts = len(invalid_transaction_amounts)

transactions = transactions[
    transactions["amount_xaf"].notna()
    & transactions["fee_xaf"].notna()
]


# remove transactions whose agent is not in the agents table
valid_agents = agents["agent_id"]

invalid_transactions = transactions[
    ~transactions["agent_id"].isin(valid_agents)
]

rejected_unknown_agents = len(invalid_transactions)

transactions = transactions[
    transactions["agent_id"].isin(valid_agents)
]


# change missing values to None
for df in [agents, services, transactions]:
    for column in amount_columns:
        if column in df.columns:
            df[column] = (
                df[column]
                .astype(object)
                .where(df[column].notna(), None)
            )


# put the data into postgres
with engine.begin() as connection:

    # load agents
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


    # load services
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


    # load transactions
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


# show what was loaded
print("Agents:", agents.shape)
print("Services:", services.shape)
print("Transactions:", transactions.shape)
print("Rejected agents:", rejected_agents)
print("Rejected services:", rejected_services)
print("Rejected transactions with invalid amounts:", rejected_amounts)
print("Rejected transactions with unknown agents:", rejected_unknown_agents)
print("Rejected invalid dates:", rejected_dates)
print("Data loaded successfully.")