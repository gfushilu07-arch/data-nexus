-- case: SQLT-XBND-009
-- Purpose: Verify prepared DDL is rejected by the translation policy before any backend execute.
-- Expected: DROP TABLE fails with a stable error; the canary row still returns on the same session.
-- Dialect: mysql

-- @step ddl
DROP TABLE sqlt_customers;
-- @step canary
SELECT 1 AS one;
