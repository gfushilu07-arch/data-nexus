-- case: SQLT-XBND-002
-- Purpose: Verify a single-parameter MySQL prepared SELECT against a PostgreSQL backend.
-- Expected: The bound customer id returns exactly one display name; the canary row returns.
-- Dialect: mysql

-- @step select
SELECT display_name FROM sqlt_customers WHERE customer_id = ?;
-- @step canary
SELECT 1 AS one;
