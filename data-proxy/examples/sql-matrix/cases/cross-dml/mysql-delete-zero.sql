-- case: SQLT-XDML-004
-- Purpose: Verify a MySQL text DELETE with no match reports zero affected rows.
-- Expected: The statement succeeds with zero affected rows and leaves all targets intact.
-- Dialect: mysql

-- @step delete
DELETE FROM sqlt_dml_targets WHERE target_id = 4999;
-- @step verify
SELECT COUNT(*) AS target_count FROM sqlt_dml_targets;
