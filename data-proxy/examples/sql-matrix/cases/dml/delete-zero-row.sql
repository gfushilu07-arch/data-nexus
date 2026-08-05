-- case: SQLT-DML-026
-- Purpose: Verify a DELETE with no matching rows is successful but has no side effect.
-- Expected: The five seeded targets remain byte-for-byte unchanged and affected rows is zero.
-- Dialect: mysql, postgres

DELETE FROM sqlt_dml_targets
WHERE target_id = 4999;
