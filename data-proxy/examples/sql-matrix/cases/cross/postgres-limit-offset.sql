-- case: SQLT-XDQL-003
-- Purpose: Verify PostgreSQL LIMIT/OFFSET remains valid through translation to MySQL.
-- Expected: The third and fourth order IDs, 1003 and 2001, are returned.
-- Dialect: postgres

SELECT order_id
FROM sqlt_orders
ORDER BY order_id
LIMIT 2 OFFSET 2;
