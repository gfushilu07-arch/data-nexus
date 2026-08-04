-- case: SQLT-DQL-048
-- Purpose: Verify LAG and LEAD expose neighboring values in a deterministic window order.
-- Expected: Each order shows the previous and next order IDs, with NULL at both boundaries.
-- Dialect: mysql, postgres

SELECT order_id,
       LAG(order_id) OVER (ORDER BY order_id) AS previous_order_id,
       LEAD(order_id) OVER (ORDER BY order_id) AS next_order_id
FROM sqlt_orders
ORDER BY order_id;
