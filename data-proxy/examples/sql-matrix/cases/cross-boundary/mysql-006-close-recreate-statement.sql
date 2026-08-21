-- case: SQLT-XBND-006
-- Purpose: Verify a closed MySQL prepared statement can be recreated from the same SQL.
-- Expected: Execute before close and execute after re-prepare return their own row counts.
-- Dialect: mysql

-- @step select
SELECT COUNT(*) AS n FROM sqlt_orders WHERE status = ?;
