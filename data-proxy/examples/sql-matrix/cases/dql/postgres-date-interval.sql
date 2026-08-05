-- case: SQLT-DQL-078
-- Purpose: Verify PostgreSQL timestamp interval arithmetic preserves exact seconds.
-- Expected: Two selected order timestamps advance by one day.
-- Dialect: postgres

SELECT order_id,
       TO_CHAR(created_at + INTERVAL '1 day', 'YYYY-MM-DD HH24:MI:SS')
FROM sqlt_orders
WHERE order_id IN (1001, 2001)
ORDER BY order_id;
