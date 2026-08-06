-- case: SQLT-INVALID-008
-- Purpose: Verify an overlength string cannot partially update a bounded column.
-- Expected: The write fails with a stable length error and the target row is unchanged.
-- Dialect: mysql, postgres

UPDATE sqlt_dml_targets
SET description = REPEAT('x', 65)
WHERE target_id = 4001;
