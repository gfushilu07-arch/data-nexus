-- case: SQLT-XBND-007
-- Purpose: Verify catalog-backed Describe and binary result format for a wildcard extended query.
-- Expected: Describe returns the six sqlt_dml_targets columns; binary target_id decodes to 4001.
-- Dialect: postgres

-- @step select
SELECT * FROM sqlt_dml_targets WHERE target_id = $1;
