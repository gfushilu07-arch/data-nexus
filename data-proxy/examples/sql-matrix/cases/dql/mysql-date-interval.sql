-- case: SQLT-DQL-079
-- Purpose: Verify MySQL timestamp interval arithmetic preserves exact seconds.
-- Expected: Two selected order timestamps advance by one day.
-- Dialect: mysql

SELECT order_id,
       DATE_FORMAT(created_at + INTERVAL 1 DAY, '%Y-%m-%d %H:%i:%s')
FROM sqlt_orders
WHERE order_id IN (1001, 2001)
ORDER BY order_id;
