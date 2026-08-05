-- case: SQLT-DML-038
-- Purpose: Verify PostgreSQL DELETE RETURNING emits the row removed from the target table.
-- Expected: Target 4004 is returned once, deleted, and reported as one affected row.
-- Dialect: postgres

DELETE FROM sqlt_dml_targets
WHERE target_id = 4004
RETURNING target_id, description, amount, status;
