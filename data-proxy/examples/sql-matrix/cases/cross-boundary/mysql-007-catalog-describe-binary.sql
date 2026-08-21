-- case: SQLT-XBND-007
-- Purpose: Verify wildcard catalog metadata and parameterized row fetch cross-protocol.
-- Expected: The six sqlt_dml_targets columns are described and the 4001 row returns.
-- Dialect: mysql

-- @step select
SELECT * FROM sqlt_dml_targets WHERE target_id = ?;
