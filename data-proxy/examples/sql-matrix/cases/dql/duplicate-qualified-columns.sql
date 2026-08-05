-- case: SQLT-DQL-072
-- Purpose: Verify duplicate output column names remain distinguishable through qualification.
-- Expected: Customer and order customer IDs match for three selected orders.
-- Dialect: mysql, postgres

SELECT customer.customer_id, orders.customer_id, orders.order_id
FROM sqlt_customers AS customer
JOIN sqlt_orders AS orders
  ON orders.customer_id = customer.customer_id
WHERE orders.order_id IN (1001, 1003, 2001)
ORDER BY orders.order_id;
