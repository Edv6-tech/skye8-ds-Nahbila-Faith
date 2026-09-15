import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def clean_text(series):
    return series.str.strip().str.upper()


def clean_status(series, replacements):
    return series.str.strip().str.lower().replace(replacements)


def clean_money(series):
    return pd.to_numeric(
        series.astype(str).str.replace(r"[^0-9.-]", "", regex=True),
        errors="coerce",
    )


def parse_dates(series):
    return pd.to_datetime(series, errors="coerce", format="mixed")


def drop_missing(df, column):
    rejected = df[column].isna().sum()
    return df[df[column].notna()], rejected


def drop_missing_any(df, columns):
    mask = df[columns].isna().any(axis=1)
    rejected = mask.sum()
    return df[~mask], rejected


def filter_known_values(df, column, known_values):
    mask = df[column].isin(known_values)
    rejected = (~mask).sum()
    return df[mask], rejected


def mask_msisdn(number):
    number = str(number).strip()
    if len(number) <= 4:
        return "X" * len(number)
    return "X" * (len(number) - 4) + number[-4:]


def nulls_to_none(df, columns):
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = df[col].astype(object).where(df[col].notna(), None)
    return df


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


def run():
    data_folder = Path(__file__).resolve().parents[1] / "data"

    load_dotenv()
    engine = create_engine(os.getenv("DATABASE_URL"))

    agents = pd.read_csv(data_folder / "agents.csv")
    services = pd.read_csv(data_folder / "services.csv")
    transactions = pd.read_csv(data_folder / "transactions.csv")

    agents = agents.drop_duplicates("agent_id")
    services = services.drop_duplicates("service_code")
    transactions = transactions.drop_duplicates("txn_id")

    agents["registered_on"] = parse_dates(agents["registered_on"])
    transactions["txn_ts"] = parse_dates(transactions["txn_ts"])

    agents, rejected_agent_dates = drop_missing(agents, "registered_on")
    transactions, rejected_txn_dates = drop_missing(transactions, "txn_ts")

    agents["agent_id"] = clean_text(agents["agent_id"])
    agents["agent_type"] = clean_text(agents["agent_type"])
    agents["status"] = clean_status(
        agents["status"],
        {"closed": "inactive", "suspended": "inactive", "open": "active"},
    )

    services["service_code"] = clean_text(services["service_code"])
    services["category"] = clean_text(services["category"])

    transactions["agent_id"] = clean_text(transactions["agent_id"])
    transactions["service_code"] = clean_text(transactions["service_code"])
    transactions["status"] = clean_text(transactions["status"])

    money_columns = ["float_limit_xaf", "base_fee_pct", "amount_xaf", "fee_xaf"]
    for table in [agents, services, transactions]:
        for col in money_columns:
            if col in table.columns:
                table[col] = clean_money(table[col])

    agents, rejected_agents = drop_missing(agents, "float_limit_xaf")
    services, rejected_services = drop_missing(services, "base_fee_pct")
    transactions, rejected_amounts = drop_missing_any(transactions, ["amount_xaf", "fee_xaf"])

    transactions, rejected_unknown_agents = filter_known_values(
        transactions, "agent_id", agents["agent_id"]
    )
    transactions, rejected_unknown_services = filter_known_values(
        transactions, "service_code", services["service_code"]
    )

    transactions["customer_msisdn"] = transactions["customer_msisdn"].apply(mask_msisdn)

    agents = nulls_to_none(agents, money_columns)
    services = nulls_to_none(services, money_columns)
    transactions = nulls_to_none(transactions, money_columns)

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

    print("Agents loaded:", agents.shape[0])
    print("Services loaded:", services.shape[0])
    print("Transactions loaded:", transactions.shape[0])
    print(
        "Transactions rejected:",
        rejected_txn_dates + rejected_amounts + rejected_unknown_agents + rejected_unknown_services,
    )
    print("Done.")


if __name__ == "__main__":
    run()