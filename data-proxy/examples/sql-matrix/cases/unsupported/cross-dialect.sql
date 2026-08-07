-- case: SQLT-UNSUPPORTED-008
-- Purpose: Pin deterministic rejection of known syntax from the other SQL dialect.
-- Expected: Direct execution returns a vendor syntax error and the gateway returns cross-dialect unsupported.
-- Dialect: mysql, postgres

-- @step postgres_cast mysql
SELECT 42::INTEGER;
-- @step mysql_identifier postgres
SELECT `customer_id` FROM sqlt_customers;
