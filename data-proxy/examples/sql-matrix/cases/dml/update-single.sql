-- case: SQLT-DML-015
-- Purpose: Verify a single-row UPDATE changes explicit columns without touching other rows.
-- Expected: Target 4001 has a new description, amount, and status; four rows are unchanged.
-- Dialect: mysql, postgres

UPDATE sqlt_dml_targets
SET description = 'alpha-updated', amount = 12.34, status = 'done'
WHERE target_id = 4001;
