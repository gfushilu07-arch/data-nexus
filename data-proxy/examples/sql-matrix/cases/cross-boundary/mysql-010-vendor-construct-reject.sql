-- case: SQLT-XBND-010
-- Purpose: Verify a MySQL vendor-only REGEXP predicate is rejected cross-protocol.
-- Expected: The prepared REGEXP query fails with a stable error; the canary row still returns.
-- Dialect: mysql

-- @step vendor
SELECT display_name FROM sqlt_customers WHERE display_name REGEXP '^A';
-- @step canary
SELECT 1 AS one;
