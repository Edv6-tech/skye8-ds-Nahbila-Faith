-- 1
SELECT agent_id, SUM(amount_xaf) AS amount_xaf
FROM transactions
GROUP BY agent_id
ORDER BY agent_id;

-- 2
SELECT agent_id, service_code, SUM(fee_xaf) AS fee_xaf
FROM transactions
GROUP BY agent_id, service_code
ORDER BY agent_id, service_code;

-- 3
SELECT status, COUNT(*) AS txn_count
FROM transactions
GROUP BY status
ORDER BY status;