-- case: SQLT-UNSUPPORTED-007
-- Purpose: Pin the gateway boundary for PostgreSQL VACUUM and ANALYZE maintenance commands.
-- Expected: Direct execution reports a missing relation and the gateway rejects both commands.
-- Dialect: postgres

-- @step vacuum postgres
VACUUM sqlt_missing_maintenance_target;
-- @step analyze postgres
ANALYZE sqlt_missing_maintenance_target;
