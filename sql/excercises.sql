-- 1. Show all the agents in the database.
SELECT *
FROM agents;


-- 2. Show only the agents that are active.
SELECT *
FROM agents
WHERE status = 'active';


-- 3. Show the agents that are from the Bui division.
SELECT *
FROM agents
WHERE division = 'Bui';


-- 4. Show the different types of agents we have.
SELECT DISTINCT agent_type
FROM agents;


-- 5. Show the 10 agents with the highest float limit.
SELECT agent_id, agent_name, float_limit_xaf
FROM agents
ORDER BY float_limit_xaf DESC
LIMIT 10;


-- 6. Find the total number of agents.
SELECT COUNT(*) AS total_agents
FROM agents;


-- 7. Find the average float limit for the agents.
SELECT AVG(float_limit_xaf) AS average_float_limit
FROM agents;


-- 8. Find the total amount of all the transactions.
SELECT SUM(amount_xaf) AS total_transaction_amount
FROM transactions;


-- 9. Find out how many agents there are for each agent type.
SELECT agent_type, COUNT(*) AS total_agents
FROM agents
GROUP BY agent_type;


-- 10. Find the agent types that have more than 100 agents.
SELECT agent_type, COUNT(*) AS total_agents
FROM agents
GROUP BY agent_type
HAVING COUNT(*) > 100;


-- 11. Show each transaction together with the name of the agent.
SELECT
    transactions.txn_id,
    transactions.agent_id,
    agents.agent_name,
    transactions.amount_xaf
FROM transactions
INNER JOIN agents
    ON transactions.agent_id = agents.agent_id;


-- 12. Show all agents and the transactions they have made.
-- Agents that have no transactions should still be shown.
SELECT
    agents.agent_id,
    agents.agent_name,
    transactions.txn_id,
    transactions.amount_xaf
FROM agents
LEFT JOIN transactions
    ON agents.agent_id = transactions.agent_id;


-- 13. Show all transactions and the agent connected to each one.
-- Transactions without a matching agent should still be shown.
SELECT
    transactions.txn_id,
    transactions.agent_id,
    agents.agent_name,
    transactions.amount_xaf
FROM agents
RIGHT JOIN transactions
    ON agents.agent_id = transactions.agent_id;


-- 14. Show all agents and all transactions, whether they match or not.
SELECT
    agents.agent_id,
    agents.agent_name,
    transactions.txn_id,
    transactions.amount_xaf
FROM agents
FULL OUTER JOIN transactions
    ON agents.agent_id = transactions.agent_id;


-- 15. Show each transaction with the name and category of its service.
SELECT
    transactions.txn_id,
    services.service_name,
    services.category,
    transactions.amount_xaf
FROM transactions
INNER JOIN services
    ON transactions.service_code = services.service_code;


-- 16. Find the agents whose float limit is higher than the average.
SELECT
    agent_id,
    agent_name,
    float_limit_xaf
FROM agents
WHERE float_limit_xaf > (
    SELECT AVG(float_limit_xaf)
    FROM agents
);


-- 17. Find transactions whose amount is higher than the average transaction amount.
SELECT
    txn_id,
    agent_id,
    amount_xaf
FROM transactions
WHERE amount_xaf > (
    SELECT AVG(amount_xaf)
    FROM transactions
);


-- 18. Show the different agent types for agents registered before 2025.
SELECT DISTINCT agent_type
FROM agents
WHERE registered_on < '2025-01-01';


-- 19. Show the different values that appear as either an agent division
-- or a service category.
SELECT division AS value
FROM agents
UNION
SELECT category AS value
FROM services;


-- 20. Find the agent IDs that are found in both agents and transactions.
SELECT agent_id
FROM agents
INTERSECT
SELECT agent_id
FROM transactions;


-- 21. Find the agents that are registered but have no transactions.
SELECT agent_id
FROM agents
EXCEPT
SELECT agent_id
FROM transactions;


-- 22. Compare the total number of agents with the number
-- of agents that have a float limit.
SELECT
    COUNT(*) AS total_agents,
    COUNT(float_limit_xaf) AS agents_with_float_limit
FROM agents;


-- 23. Compare the total transactions with transactions
-- that have an amount recorded.
SELECT
    COUNT(*) AS total_transactions,
    COUNT(amount_xaf) AS transactions_with_amount
FROM transactions;


-- 24. Show how joining agents and transactions can multiply rows.
-- Before the join, an agent has one row in the agents table.
-- After the join, an agent can appear once for every transaction.
SELECT
    agents.agent_id,
    agents.agent_name,
    COUNT(transactions.txn_id) AS number_of_transactions
FROM agents
INNER JOIN transactions
    ON agents.agent_id = transactions.agent_id
GROUP BY agents.agent_id, agents.agent_name
ORDER BY number_of_transactions DESC;


-- 25. Show how joining services and transactions can multiply rows.
-- Before the join, a service has one row in the services table.
-- After the join, a service can appear once for every transaction.
SELECT
    services.service_code,
    services.service_name,
    COUNT(transactions.txn_id) AS number_of_transactions
FROM services
INNER JOIN transactions
    ON services.service_code = transactions.service_code
GROUP BY services.service_code, services.service_name
ORDER BY number_of_transactions DESC;