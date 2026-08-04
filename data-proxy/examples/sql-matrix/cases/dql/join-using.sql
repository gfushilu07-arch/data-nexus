-- case: SQLT-DQL-030
-- Purpose: Verify JOIN USING merges the shared join key into one projected column.
-- Expected: Six customer-order pairs are returned in order_id order.
-- Dialect: mysql, postgres

SELECT customer_id, display_name, order_id
FROM sqlt_customers
JOIN sqlt_orders USING (customer_id)
ORDER BY order_id;
