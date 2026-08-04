-- case: SQLT-DQL-032
-- Purpose: Verify qualified projections can return duplicate result column names safely.
-- Expected: One row contains customer_id 101 from both joined relations.
-- Dialect: mysql, postgres

SELECT c.customer_id, o.customer_id
FROM sqlt_customers AS c
JOIN sqlt_orders AS o ON o.customer_id = c.customer_id
WHERE o.order_id = 1001;
