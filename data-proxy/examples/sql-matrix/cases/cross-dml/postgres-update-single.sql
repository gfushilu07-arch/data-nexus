-- case: SQLT-XDML-002
-- Purpose: Verify a PostgreSQL simple UPDATE reaches a MySQL backend with exact affected rows.
-- Expected: One target row is changed and immediately visible on the same connection.
-- Dialect: postgres

-- @step update
UPDATE sqlt_dml_targets
SET description = 'alpha-updated', amount = 12.34, status = 'done'
WHERE target_id = 4001;
-- @step verify
SELECT target_id, description, amount, status
FROM sqlt_dml_targets WHERE target_id = 4001;
