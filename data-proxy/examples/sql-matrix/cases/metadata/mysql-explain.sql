-- case: SQLT-META-008
-- Purpose: Verify MySQL EXPLAIN classifies a filtered ordered query without executing it.
-- Expected: Allow returns a plan for sqlt_orders; fixture data remains unchanged.
-- Dialect: mysql

EXPLAIN SELECT order_id, total_amount
FROM sqlt_orders
WHERE tenant_id = 10
ORDER BY order_id;
