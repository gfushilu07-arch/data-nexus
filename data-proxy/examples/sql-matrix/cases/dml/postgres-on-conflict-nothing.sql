-- case: SQLT-DML-031
-- Purpose: Verify PostgreSQL ON CONFLICT DO NOTHING skips an existing primary key.
-- Expected: No target row changes and affected rows is zero.
-- Dialect: postgres

INSERT INTO sqlt_dml_targets
    (target_id, customer_id, tenant_id, description, amount, status)
VALUES
    (4001, 101, 10, 'conflict-ignored', 91.00, 'ignored')
ON CONFLICT (target_id) DO NOTHING;
