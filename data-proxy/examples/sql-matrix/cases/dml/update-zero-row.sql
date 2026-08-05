-- case: SQLT-DML-019
-- Purpose: Verify an UPDATE with no matching rows is successful but has no side effect.
-- Expected: The five seeded targets remain byte-for-byte unchanged and affected rows is zero.
-- Dialect: mysql, postgres

UPDATE sqlt_dml_targets
SET status = 'unreachable'
WHERE target_id = 4999;
