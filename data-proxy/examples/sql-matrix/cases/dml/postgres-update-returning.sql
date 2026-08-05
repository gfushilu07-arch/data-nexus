-- case: SQLT-DML-037
-- Purpose: Verify PostgreSQL UPDATE RETURNING emits the updated row with exact values.
-- Expected: Target 4002 is updated, returned once, and reported as one affected row.
-- Dialect: postgres

UPDATE sqlt_dml_targets
SET description = 'returned-update',
    amount = 97.50,
    status = 'returned'
WHERE target_id = 4002
RETURNING target_id, description, amount, status;
