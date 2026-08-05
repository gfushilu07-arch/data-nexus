-- case: SQLT-DML-035
-- Purpose: Verify MySQL REPLACE deletes and reinserts an existing primary-key row.
-- Expected: Target 4001 contains the replacement row and affected rows is two.
-- Dialect: mysql

REPLACE INTO sqlt_dml_targets
    (target_id, customer_id, tenant_id, description, amount, status)
VALUES
    (4001, 101, 10, 'replaced', 95.00, 'replaced');
