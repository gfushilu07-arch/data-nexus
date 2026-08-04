-- case: SQLT-DQL-018
-- Purpose: Verify grouping by a text value with count and sum aggregates.
-- Expected: One summary row per order status is returned in status order.
-- Dialect: mysql, postgres

SELECT status, COUNT(*) AS order_count, SUM(total_amount) AS amount_sum
FROM sqlt_orders
GROUP BY status
ORDER BY status;
