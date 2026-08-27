-- 1. all agents
SELECT *
FROM agents;


-- 2. active agents only
SELECT *
FROM agents
WHERE status = 'active';


-- 3. agents from Bui division
SELECT *
FROM agents
WHERE division = 'Bui';


-- 4. distinct agent types
SELECT DISTINCT agent_type
FROM agents;


-- 5. top 10 agents by float limit
SELECT agent_id, agent_name, float_limit_xaf
FROM agents
ORDER BY float_limit_xaf DESC
LIMIT 10;


-- 6. total agents
SELECT COUNT(*) AS total_agents
FROM agents;


-- 7. average float limit
SELECT AVG(float_limit_xaf) AS average_float_limit
FROM agents;


-- 8. total transaction amount
SELECT SUM(amount_xaf) AS total_transaction_amount
FROM transactions;


-- 9. agent count per type
SELECT agent_type, COUNT(*) AS total_agents
FROM agents
GROUP BY agent_type;


-- 10. agent types with more than 100 agents
SELECT agent_type, COUNT(*) AS total_agents
FROM agents
GROUP BY agent_type
HAVING COUNT(*) > 100;


-- 11. transactions with agent name (inner join)
SELECT
    transactions.txn_id,
    transactions.agent_id,
    agents.agent_name,
    transactions.amount_xaf
FROM transactions
INNER JOIN agents
    ON transactions.agent_id = agents.agent_id;


-- 12. all agents + their transactions, agents with none still show (left join)
SELECT
    agents.agent_id,
    agents.agent_name,
    transactions.txn_id,
    transactions.amount_xaf
FROM agents
LEFT JOIN transactions
    ON agents.agent_id = transactions.agent_id;


-- 13. all transactions + their agent, unmatched transactions still show (right join)
SELECT
    transactions.txn_id,
    transactions.agent_id,
    agents.agent_name,
    transactions.amount_xaf
FROM agents
RIGHT JOIN transactions
    ON agents.agent_id = transactions.agent_id;


-- 14. all agents and all transactions either way (full outer join)
SELECT
    agents.agent_id,
    agents.agent_name,
    transactions.txn_id,
    transactions.amount_xaf
FROM agents
FULL OUTER JOIN transactions
    ON agents.agent_id = transactions.agent_id;


-- 15. transactions with service name/category
SELECT
    transactions.txn_id,
    services.service_name,
    services.category,
    transactions.amount_xaf
FROM transactions
INNER JOIN services
    ON transactions.service_code = services.service_code;


-- 16. agents above average float limit (subquery)
SELECT
    agent_id,
    agent_name,
    float_limit_xaf
FROM agents
WHERE float_limit_xaf > (
    SELECT AVG(float_limit_xaf)
    FROM agents
);


-- 17. transactions above average amount (subquery)
SELECT
    txn_id,
    agent_id,
    amount_xaf
FROM transactions
WHERE amount_xaf > (
    SELECT AVG(amount_xaf)
    FROM transactions
);


-- 18. agent types registered before 2025
SELECT DISTINCT agent_type
FROM agents
WHERE registered_on < '2025-01-01';


-- 19. divisions and service categories combined (union)
SELECT division AS value
FROM agents
UNION
SELECT category AS value
FROM services;


-- 20. agent ids in both agents and transactions (intersect)
SELECT agent_id
FROM agents
INTERSECT
SELECT agent_id
FROM transactions;


-- 21. agents with no transactions (except)
SELECT agent_id
FROM agents
EXCEPT
SELECT agent_id
FROM transactions;


-- 22. total agents vs agents with a float limit (NULL check via COUNT)
SELECT
    COUNT(*) AS total_agents,
    COUNT(float_limit_xaf) AS agents_with_float_limit
FROM agents;


-- 23. total transactions vs transactions with an amount (NULL check via COUNT)
SELECT
    COUNT(*) AS total_transactions,
    COUNT(amount_xaf) AS transactions_with_amount
FROM transactions;


-- 24. agents before join
SELECT COUNT(*) FROM agents;
-- 1,055

-- agents after joining to transactions - way more rows now
SELECT COUNT(*)
FROM agents
INNER JOIN transactions
    ON agents.agent_id = transactions.agent_id;


-- 25. services before join
SELECT COUNT(*) FROM services;
-- 18

-- services after joining to transactions 
SELECT COUNT(*)
FROM services
INNER JOIN transactions
    ON services.service_code = transactions.service_code;


-- 26. total amount per agent, checked against pandas - matches
SELECT agent_id, SUM(amount_xaf) AS amount_xaf
FROM transactions
GROUP BY agent_id
ORDER BY agent_id;


-- 27. fee per agent per service, checked against pandas - matches
SELECT agent_id, service_code, SUM(fee_xaf) AS fee_xaf
FROM transactions
GROUP BY agent_id, service_code
ORDER BY agent_id, service_code;


-- 28. count per status, checked against pandas - matches
SELECT status, COUNT(*) AS txn_count
FROM transactions
GROUP BY status
ORDER BY status;