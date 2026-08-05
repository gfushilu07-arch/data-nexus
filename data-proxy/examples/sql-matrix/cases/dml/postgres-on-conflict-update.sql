-- case: SQLT-DML-032
-- Purpose: Verify PostgreSQL ON CONFLICT DO UPDATE applies excluded values to an existing row.
-- Expected: Target 4001 receives the replacement values and affected rows is one.
-- Dialect: postgres

INSERT INTO sqlt_dml_targets
    (target_id, customer_id, tenant_id, description, amount, status)
VALUES
    (4001, 101, 10, 'conflict-updated', 92.00, 'upserted')
ON CONFLICT (target_id) DO UPDATE
SET description = EXCLUDED.description,
    amount = EXCLUDED.amount,
    status = EXCLUDED.status;
