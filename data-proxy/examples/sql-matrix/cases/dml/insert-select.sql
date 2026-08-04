-- case: SQLT-DML-010
-- Purpose: Verify INSERT ... SELECT preserves source rows and converts tenant IDs to exact amounts.
-- Expected: Four mutations are inserted from the four deterministic customer rows.
-- Dialect: mysql, postgres

INSERT INTO sqlt_mutations (mutation_id, description, amount, status)
SELECT customer_id + 3000, display_name, tenant_id * 1.00, 'copied'
FROM sqlt_customers
ORDER BY customer_id;
