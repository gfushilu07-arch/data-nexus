-- case: SQLT-DML-027
-- Purpose: Verify DELETE can select target customers through a subquery.
-- Expected: Target 4002, whose customer email is NULL, is absent; four targets remain.
-- Dialect: mysql, postgres

DELETE FROM sqlt_dml_targets
WHERE customer_id IN (
    SELECT customer_id FROM sqlt_customers WHERE email IS NULL
);
