-- case: SQLT-XDQL-003
-- Purpose: Verify MySQL LIMIT offset,count is rewritten for a PostgreSQL backend.
-- Expected: The third and fourth order IDs, 1003 and 2001, are returned.
-- Dialect: mysql

SELECT order_id
FROM sqlt_orders
ORDER BY order_id
LIMIT 2, 2;
