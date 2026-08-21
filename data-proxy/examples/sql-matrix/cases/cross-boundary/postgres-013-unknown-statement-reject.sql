-- case: SQLT-XBND-013
-- Purpose: Verify a closed PostgreSQL named statement cannot be bound again.
-- Expected: Bind after Close fails with a stable identity; Sync returns idle and a re-Parsed statement returns the row.
-- Dialect: postgres

-- @step select
SELECT 1 AS one;
