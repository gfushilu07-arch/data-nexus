-- case: SQLT-DML-033
-- Purpose: Verify MySQL ON DUPLICATE KEY UPDATE changes an existing primary-key row.
-- Expected: Target 4001 receives the requested values and affected rows is two.
-- Dialect: mysql

INSERT INTO sqlt_dml_targets
    (target_id, customer_id, tenant_id, description, amount, status)
VALUES
    (4001, 101, 10, 'duplicate-updated', 93.00, 'upserted')
ON DUPLICATE KEY UPDATE
    description = 'duplicate-updated',
    amount = 93.00,
    status = 'upserted';
