-- case: SQLT-META-019
-- Purpose: Verify PostgreSQL EXPLAIN returns a plan without executing the query.
-- Expected: Allow returns a text plan for sqlt_orders; fixture data is unchanged.
-- Dialect: postgres

EXPLAIN (FORMAT TEXT)
SELECT order_id, total_amount
FROM sqlt_orders
WHERE tenant_id = 10
ORDER BY order_id;
