-- case: SQLT-DQL-042
-- Purpose: Verify UNION ALL preserves duplicate rows from both query operands.
-- Expected: Tenant ID 10 is returned twice.
-- Dialect: mysql, postgres

SELECT tenant_id FROM sqlt_customers WHERE customer_id = 101
UNION ALL
SELECT tenant_id FROM sqlt_orders WHERE order_id = 1001
ORDER BY tenant_id;
