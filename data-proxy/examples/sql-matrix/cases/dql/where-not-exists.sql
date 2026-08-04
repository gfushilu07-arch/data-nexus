-- case: SQLT-DQL-015
-- Purpose: Verify a correlated NOT EXISTS predicate with an empty matching relation.
-- Expected: Zero rows are returned because every fixture customer owns an order.
-- Dialect: mysql, postgres

SELECT c.customer_id
FROM sqlt_customers AS c
WHERE NOT EXISTS (
    SELECT 1
    FROM sqlt_orders AS o
    WHERE o.customer_id = c.customer_id
)
ORDER BY c.customer_id;
