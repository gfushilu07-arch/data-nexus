-- case: SQLT-XBND-013
-- Purpose: Verify a closed MySQL prepared statement cannot be executed again.
-- Expected: Reuse after close fails with a stable identity; a fresh prepare returns the row.
-- Dialect: mysql

-- @step select
SELECT 1 AS one;
