-- case: SQLT-XBND-009
-- Purpose: Verify extended DDL execute is rejected by the translation policy before backend execute.
-- Expected: The DROP TABLE execute fails with a stable error; Sync returns idle and the canary row returns.
-- Dialect: postgres

-- @step ddl
DROP TABLE sqlt_customers;
-- @step canary
SELECT 1 AS one;
