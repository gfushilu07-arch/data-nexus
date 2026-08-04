-- case: SQLT-DQL-014
-- Purpose: Verify a correlated EXISTS predicate against related order rows.
-- Expected: All four customers are returned because each has at least one fixture order.
-- Dialect: mysql, postgres

SELECT c.customer_id
FROM sqlt_customers AS c
WHERE EXISTS (
    SELECT 1
    FROM sqlt_orders AS o
    WHERE o.customer_id = c.customer_id
)
ORDER BY c.customer_id;
