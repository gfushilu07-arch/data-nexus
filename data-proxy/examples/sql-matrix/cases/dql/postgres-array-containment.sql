-- case: SQLT-DQL-074
-- Purpose: Verify PostgreSQL array containment can filter scalar tenant values.
-- Expected: Only tenant 10 customers are returned in primary-key order.
-- Dialect: postgres

SELECT customer_id, tenant_id
FROM sqlt_customers
WHERE ARRAY[tenant_id] <@ ARRAY[10, 30]
ORDER BY customer_id;
