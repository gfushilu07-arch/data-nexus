-- case: SQLT-XBND-007
-- Purpose: Verify catalog-backed Describe and binary result format cross-protocol.
-- Expected: Describe returns the six sqlt_dml_targets columns; the binary int8 fetch decodes to 4001.
-- Dialect: postgres

-- @step select
SELECT * FROM sqlt_dml_targets WHERE target_id = $1;
-- @step binary_fetch
SELECT target_id FROM sqlt_dml_targets WHERE target_id = $1;
