-- case: SQLT-DML-018
-- Purpose: Verify UPDATE can write an explicit NULL to the nullable amount column.
-- Expected: Target 4001 has NULL amount and status missing; all other targets are unchanged.
-- Dialect: mysql, postgres

UPDATE sqlt_dml_targets
SET amount = NULL, status = 'missing'
WHERE target_id = 4001;
