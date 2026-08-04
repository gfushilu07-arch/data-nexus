-- case: SQLT-DQL-024
-- Purpose: Verify LIMIT and OFFSET after a stable ascending sort.
-- Expected: The third and fourth order IDs, 1003 and 2001, are returned.
-- Dialect: mysql, postgres

SELECT order_id
FROM sqlt_orders
ORDER BY order_id
LIMIT 2 OFFSET 2;
