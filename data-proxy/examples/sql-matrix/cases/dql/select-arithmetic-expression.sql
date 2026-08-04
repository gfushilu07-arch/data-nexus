-- case: SQLT-DQL-007
-- Purpose: Verify decimal arithmetic expressions and computed-column aliases.
-- Expected: Each order amount is doubled exactly and rows remain in order_id order.
-- Dialect: mysql, postgres

SELECT order_id, total_amount, total_amount * 2 AS doubled_amount
FROM sqlt_orders
ORDER BY order_id;
