-- case: SQLT-DQL-011
-- Purpose: Verify inclusive decimal range filtering with BETWEEN.
-- Expected: Orders from 10.00 through 50.00 inclusive are returned in order_id order.
-- Dialect: mysql, postgres

SELECT order_id, total_amount
FROM sqlt_orders
WHERE total_amount BETWEEN 10.00 AND 50.00
ORDER BY order_id;
