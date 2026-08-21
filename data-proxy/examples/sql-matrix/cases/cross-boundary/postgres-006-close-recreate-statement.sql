-- case: SQLT-XBND-006
-- Purpose: Verify a closed PostgreSQL named statement can be re-Parsed from the same SQL.
-- Expected: Execute before close and execute after re-Parse return their own row counts.
-- Dialect: postgres

-- @step select
SELECT COUNT(*) AS n FROM sqlt_orders WHERE status = $1;
