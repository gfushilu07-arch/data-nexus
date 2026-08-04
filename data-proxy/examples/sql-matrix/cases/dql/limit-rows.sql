-- case: SQLT-DQL-023
-- Purpose: Verify LIMIT after a stable ascending sort.
-- Expected: The first two order IDs, 1001 and 1002, are returned.
-- Dialect: mysql, postgres

SELECT order_id
FROM sqlt_orders
ORDER BY order_id
LIMIT 2;
