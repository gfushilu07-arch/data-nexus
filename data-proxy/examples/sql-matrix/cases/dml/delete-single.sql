-- case: SQLT-DML-024
-- Purpose: Verify a single-row DELETE removes only the requested target.
-- Expected: Target 4001 is absent and the other four targets remain unchanged.
-- Dialect: mysql, postgres

DELETE FROM sqlt_dml_targets
WHERE target_id = 4001;
