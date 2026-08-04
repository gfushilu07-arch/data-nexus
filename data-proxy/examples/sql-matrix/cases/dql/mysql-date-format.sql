-- case: SQLT-DQL-059
-- Purpose: Verify MySQL DATE_FORMAT renders a deterministic timestamp label.
-- Expected: Each order returns an ISO-like year-month label in order_id order.
-- Dialect: mysql

SELECT order_id,
       DATE_FORMAT(created_at, '%Y-%m') AS created_month
FROM sqlt_orders
ORDER BY order_id;
