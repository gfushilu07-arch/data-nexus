-- case: SQLT-XBND-001
-- Purpose: Verify a zero-parameter PostgreSQL extended SELECT lifecycle through a MySQL backend.
-- Expected: Parse, Bind, Execute, and Sync succeed; both ordered order rows and the canary row return.
-- Dialect: postgres

-- @step select
SELECT order_id, total_amount, status FROM sqlt_orders
WHERE customer_id = 101 ORDER BY order_id;
-- @step canary
SELECT 1 AS one;
