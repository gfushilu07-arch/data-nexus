-- case: SQLT-DQL-043
-- Purpose: Verify INTERSECT returns customer IDs present in both query operands.
-- Expected: Customers 101, 201, and 202 are returned because they own paid orders.
-- Dialect: mysql, postgres

SELECT customer_id FROM sqlt_customers
INTERSECT
SELECT customer_id FROM sqlt_orders WHERE status = 'paid'
ORDER BY customer_id;
