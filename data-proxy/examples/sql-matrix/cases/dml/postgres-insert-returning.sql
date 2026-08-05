-- case: SQLT-DML-036
-- Purpose: Verify PostgreSQL INSERT RETURNING emits the inserted row with exact values.
-- Expected: Target 4010 is inserted, returned once, and reported as one affected row.
-- Dialect: postgres

INSERT INTO sqlt_dml_targets
    (target_id, customer_id, tenant_id, description, amount, status)
VALUES
    (4010, 101, 10, 'returned-insert', 96.00, 'returned')
RETURNING target_id, description, amount, status;
