-- Q1. what share of agents are still active 1 to 6 months after they signed up

WITH cohorts AS (
    SELECT
        agent_id,
        DATE_TRUNC('month', registered_on) AS cohort_month
    FROM agents
),
cohort_sizes AS (
    SELECT
        cohort_month,
        COUNT(*) AS cohort_size
    FROM cohorts
    GROUP BY cohort_month
),
agent_activity_months AS (
    SELECT DISTINCT
        c.agent_id,
        c.cohort_month,
        DATE_TRUNC('month', t.txn_ts) AS activity_month
    FROM cohorts c
    JOIN transactions t ON t.agent_id = c.agent_id
),
month_offsets AS (
    -- months since registration, e.g. registered jan, txn in march = 2
    SELECT
        agent_id,
        cohort_month,
        (EXTRACT(YEAR FROM activity_month) - EXTRACT(YEAR FROM cohort_month)) * 12
          + (EXTRACT(MONTH FROM activity_month) - EXTRACT(MONTH FROM cohort_month)) AS month_number
    FROM agent_activity_months
),
retained AS (
    SELECT
        cohort_month,
        month_number,
        COUNT(DISTINCT agent_id) AS active_agents
    FROM month_offsets
    WHERE month_number BETWEEN 1 AND 6
    GROUP BY cohort_month, month_number
)
SELECT
    r.cohort_month,
    r.month_number,
    r.active_agents,
    s.cohort_size,
    ROUND(r.active_agents::numeric / s.cohort_size, 4) AS retention_rate
FROM retained r
JOIN cohort_sizes s ON s.cohort_month = r.cohort_month
ORDER BY r.cohort_month, r.month_number;


-- Q2. running fee revenue total + 7 day average daily transaction volume

WITH daily AS (
    SELECT
        DATE_TRUNC('day', txn_ts)::date AS txn_date,
        SUM(fee_xaf) AS daily_fee,
        COUNT(*) AS daily_txn_count
    FROM transactions
    GROUP BY DATE_TRUNC('day', txn_ts)::date
)
SELECT
    txn_date,
    daily_fee,
    SUM(daily_fee) OVER (ORDER BY txn_date) AS running_fee_total,
    daily_txn_count,
    AVG(daily_txn_count) OVER (
        ORDER BY txn_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS moving_avg_7day_txn_volume
FROM daily
ORDER BY txn_date;


-- Q3. who are the top 3 agents by value in each division

WITH agent_value AS (
    SELECT
        a.division,
        a.agent_id,
        a.agent_name,
        SUM(t.amount_xaf) AS total_value
    FROM agents a
    JOIN transactions t ON t.agent_id = a.agent_id
    GROUP BY a.division, a.agent_id, a.agent_name
),
ranked AS (
    SELECT
        division,
        agent_id,
        agent_name,
        total_value,
        RANK() OVER (PARTITION BY division ORDER BY total_value DESC) AS division_rank
    FROM agent_value
)
SELECT *
FROM ranked
WHERE division_rank <= 3
ORDER BY division, division_rank;


-- Q4. which agents are bringing in more than the average agent

-- nested - agent_totals gets calculated twice
SELECT agent_id, agent_name
FROM agents
WHERE agent_id IN (
    SELECT agent_id
    FROM (
        SELECT agent_id, SUM(amount_xaf) AS total_value
        FROM transactions
        GROUP BY agent_id
    ) agent_totals
    WHERE total_value > (
        SELECT AVG(total_value)
        FROM (
            SELECT agent_id, SUM(amount_xaf) AS total_value
            FROM transactions
            GROUP BY agent_id
        ) inner_totals
    )
);

-- CTE version - agent_totals only calculated once
WITH agent_totals AS (
    SELECT agent_id, SUM(amount_xaf) AS total_value
    FROM transactions
    GROUP BY agent_id
),
avg_total AS (
    SELECT AVG(total_value) AS avg_value
    FROM agent_totals
)
SELECT a.agent_id, a.agent_name, t.total_value
FROM agents a
JOIN agent_totals t ON t.agent_id = a.agent_id
CROSS JOIN avg_total
WHERE t.total_value > avg_total.avg_value;



-- Q5. is this query too slow, and does adding an index fix it

-- before index
EXPLAIN ANALYZE
SELECT * FROM transactions WHERE agent_id = 'A0001';
-- --QUERY PLAN
-- Seq Scan on transactions  (cost=0.00..3825.56 rows=109 width=57) (actual time=91.266..91.266 rows=0 loops=1)
--   Filter: ((agent_id)::text = 'A0001'::text)
--   Rows Removed by Filter: 160285
-- Planning Time: 3.125 ms
-- Execution Time: 91.293 ms


CREATE INDEX idx_transactions_agent_id ON transactions (agent_id);

-- after index, same query again
EXPLAIN ANALYZE
SELECT * FROM transactions WHERE agent_id = 'A0001';
-- QUERY PLAN
-- Bitmap Heap Scan on transactions  (cost=5.14..353.80 rows=109 width=57) (actual time=0.428..0.429 rows=0 loops=1)
--   Recheck Cond: ((agent_id)::text = 'A0001'::text)
--   ->  Bitmap Index Scan on idx_transactions_agent_id  (cost=0.00..5.11 rows=109 width=0) (actual time=0.420..0.420 rows=0 loops=1)
--         Index Cond: ((agent_id)::text = 'A0001'::text)
-- Planning Time: 4.839 ms
-- Execution Time: 0.524 ms
