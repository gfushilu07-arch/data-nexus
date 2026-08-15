-- case: SQLT-XDML-003
-- Purpose: Verify a PostgreSQL simple DELETE removes one MySQL backend row.
-- Expected: One row is affected and the target is absent on the same connection.
-- Dialect: postgres

-- @step delete
DELETE FROM sqlt_dml_targets WHERE target_id = 4001;
-- @step verify
SELECT COUNT(*) AS remaining FROM sqlt_dml_targets WHERE target_id = 4001;
