-- case: SQLT-DML-034
-- Purpose: Verify MySQL INSERT IGNORE skips an existing primary key without changing its row.
-- Expected: No target row changes and affected rows is zero.
-- Dialect: mysql

INSERT IGNORE INTO sqlt_dml_targets
    (target_id, customer_id, tenant_id, description, amount, status)
VALUES
    (4001, 101, 10, 'ignore-duplicate', 94.00, 'ignored');
