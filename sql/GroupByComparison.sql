-- 1. Total transaction amount for each status
SELECT
    status,
    SUM(amount_xaf) AS amount_xaf
FROM transactions
GROUP BY status
ORDER BY status;


-- 2. Count how many transactions each service has
SELECT
    service_code,
    COUNT(*) AS transaction_count
FROM transactions
GROUP BY service_code
ORDER BY service_code;


-- 3. Count how many agents there are for each agent type
SELECT
    agent_type,
    COUNT(*) AS agent_count
FROM agents
GROUP BY agent_type
ORDER BY agent_type;