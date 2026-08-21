-- case: SQLT-XBND-001
-- Purpose: Verify a zero-parameter MySQL prepared SELECT lifecycle through a PostgreSQL backend.
-- Expected: Prepare, execute, and close succeed; both ordered order rows and the canary row return.
-- Dialect: mysql

-- @step select
SELECT order_id, total_amount, status FROM sqlt_orders
WHERE customer_id = 101 ORDER BY order_id;
-- @step canary
SELECT 1 AS one;
