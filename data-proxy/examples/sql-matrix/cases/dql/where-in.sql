-- case: SQLT-DQL-010
-- Purpose: Verify membership filtering with an IN value list.
-- Expected: Orders whose status is pending or refunded are returned in order_id order.
-- Dialect: mysql, postgres

SELECT order_id, status
FROM sqlt_orders
WHERE status IN ('pending', 'refunded')
ORDER BY order_id;
