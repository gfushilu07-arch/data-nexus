-- case: SQLT-DQL-070
-- Purpose: Verify an alias wildcard remains scoped when joined with another relation.
-- Expected: Customer columns and selected order IDs are returned in order ID order.
-- Dialect: mysql, postgres

SELECT customer.*, orders.order_id
FROM sqlt_customers AS customer
JOIN sqlt_orders AS orders
  ON orders.customer_id = customer.customer_id
WHERE orders.order_id IN (1001, 1003, 2001)
ORDER BY orders.order_id;
