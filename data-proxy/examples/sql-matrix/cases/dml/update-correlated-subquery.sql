-- case: SQLT-DML-021
-- Purpose: Verify a correlated UPDATE subquery aggregates orders for each target customer.
-- Expected: All tenant 10 targets receive their customer's exact order total and rollup status.
-- Dialect: mysql, postgres

UPDATE sqlt_dml_targets AS t
SET amount = (
        SELECT COALESCE(SUM(o.total_amount), 0)
        FROM sqlt_orders AS o
        WHERE o.customer_id = t.customer_id
    ),
    status = 'rollup'
WHERE t.tenant_id = 10;
