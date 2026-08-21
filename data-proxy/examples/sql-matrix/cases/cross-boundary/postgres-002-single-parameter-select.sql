-- case: SQLT-XBND-002
-- Purpose: Verify a single-parameter PostgreSQL extended SELECT against a MySQL backend.
-- Expected: The bound customer id returns exactly one display name; the canary row returns.
-- Dialect: postgres

-- @step select
SELECT display_name FROM sqlt_customers WHERE customer_id = $1;
-- @step canary
SELECT 1 AS one;
