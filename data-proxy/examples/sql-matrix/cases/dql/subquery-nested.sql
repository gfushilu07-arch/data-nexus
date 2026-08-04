-- case: SQLT-DQL-037
-- Purpose: Verify nested scalar subqueries preserve scope across three query levels.
-- Expected: Customer 202 is returned because order 2003 has the global maximum amount.
-- Dialect: mysql, postgres

SELECT customer_id
FROM sqlt_customers
WHERE customer_id = (
    SELECT customer_id
    FROM sqlt_orders
    WHERE total_amount = (
        SELECT MAX(total_amount)
        FROM sqlt_orders
    )
);
