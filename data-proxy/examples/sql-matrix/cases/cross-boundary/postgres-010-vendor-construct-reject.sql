-- case: SQLT-XBND-010
-- Purpose: Verify a PostgreSQL vendor-only ILIKE predicate is rejected cross-protocol.
-- Expected: The extended ILIKE execute fails with a stable error; Sync returns idle and the canary row returns.
-- Dialect: postgres

-- @step vendor
SELECT display_name FROM sqlt_customers WHERE display_name ILIKE 'a%';
-- @step canary
SELECT 1 AS one;
