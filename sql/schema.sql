CREATE TABLE agents (
    agent_id VARCHAR(20) PRIMARY KEY,
    agent_name VARCHAR(100) NOT NULL,
    town VARCHAR(100) NOT NULL,
    division VARCHAR(100) NOT NULL,
    registered DATE NOT NULL,
    agent_type VARCHAR(50) NOT NULL,
    float_limit DECIMAL(15, 2) NOT NULL CHECK (float_limit >= 0),
    status VARCHAR(20) NOT NULL CHECK (status IN ('active', 'inactive'))
);


CREATE TABLE services (
    service_code VARCHAR(20) PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    base_fee_pct DECIMAL(5, 2) NOT NULL
        CHECK (base_fee_pct >= 0 AND base_fee_pct <= 100)
);


CREATE TABLE transactions (
    txn_id VARCHAR(30) PRIMARY KEY,
    agent_id VARCHAR(20) NOT NULL,
    service_code VARCHAR(20) NOT NULL,
    txn_ts TIMESTAMP NOT NULL,
    amount_xaf DECIMAL(15, 2) NOT NULL CHECK (amount_xaf >= 0),
    fee_xaf DECIMAL(15, 2) NOT NULL CHECK (fee_xaf >= 0),
    status VARCHAR(20) NOT NULL
        CHECK (status IN ('SUCCESS', 'FAILED', 'REVERSED')),
    customer_msisdn VARCHAR(20) NOT NULL,

    CONSTRAINT fk_transaction_agent
        FOREIGN KEY (agent_id)
        REFERENCES agents(agent_id),

    CONSTRAINT fk_transaction_service
        FOREIGN KEY (service_code)
        REFERENCES services(service_code)
);