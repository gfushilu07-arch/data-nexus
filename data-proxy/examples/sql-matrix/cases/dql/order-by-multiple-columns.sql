-- case: SQLT-DQL-022
-- Purpose: Verify mixed-direction ordering with a deterministic tie-breaker.
-- Expected: Orders are sorted by tenant ascending, amount descending, then order_id ascending.
-- Dialect: mysql, postgres

SELECT tenant_id, order_id, total_amount
FROM sqlt_orders
ORDER BY tenant_id ASC, total_amount DESC, order_id ASC;
