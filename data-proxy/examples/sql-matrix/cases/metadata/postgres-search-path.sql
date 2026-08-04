-- case: SQLT-META-020
-- Purpose: Verify PostgreSQL SET search_path changes only the current session.
-- Expected: The follow-up SHOW returns public without persistent schema changes.
-- Dialect: postgres

SET search_path TO public;
SHOW search_path;
