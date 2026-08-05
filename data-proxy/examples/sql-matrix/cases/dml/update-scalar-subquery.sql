-- case: SQLT-DML-020
-- Purpose: Verify UPDATE can use a scalar subquery from the seeded orders table.
-- Expected: Target 4001 receives order 1001's exact amount and copied status.
-- Dialect: mysql, postgres

UPDATE sqlt_dml_targets
SET amount = (SELECT total_amount FROM sqlt_orders WHERE order_id = 1001),
    status = 'copied'
WHERE target_id = 4001;
