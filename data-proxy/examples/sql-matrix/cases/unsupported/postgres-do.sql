-- case: SQLT-UNSUPPORTED-003
-- Purpose: Pin the fail-closed boundary for PostgreSQL anonymous code blocks.
-- Expected: Direct execution raises a fixed sentinel error and the gateway rejects the DO capability.
-- Dialect: postgres

DO $sqlt$ BEGIN RAISE EXCEPTION 'sqlt-do-sentinel'; END $sqlt$;
