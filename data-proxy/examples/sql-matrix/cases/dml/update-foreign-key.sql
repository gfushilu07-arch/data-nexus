-- case: SQLT-DML-030
-- Purpose: Verify UPDATE rejects a foreign-key change and leaves the target table unchanged.
-- Expected: The backend reports a stable foreign-key error and no target row is modified.
-- Dialect: mysql, postgres

UPDATE sqlt_dml_targets
SET customer_id = 999
WHERE target_id = 4001;
