-- case: SQLT-DML-017
-- Purpose: Verify an UPDATE expression performs exact decimal arithmetic on matching rows.
-- Expected: Both ready rows gain 5.25, including the NULL amount through COALESCE.
-- Dialect: mysql, postgres

UPDATE sqlt_dml_targets
SET amount = COALESCE(amount, 0) + 5.25
WHERE status = 'ready';
