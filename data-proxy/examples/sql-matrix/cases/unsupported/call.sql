-- case: SQLT-UNSUPPORTED-004
-- Purpose: Pin the fail-closed boundary for stored procedure invocation in both dialects.
-- Expected: Direct execution reports a missing procedure and the gateway rejects before lookup.
-- Dialect: mysql, postgres

-- @step call mysql
CALL sqlt_missing_procedure();
-- @step call postgres
CALL sqlt_missing_procedure();
