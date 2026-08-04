-- case: SQLT-DQL-031
-- Purpose: Verify NATURAL JOIN matches all shared customer_id and tenant_id columns.
-- Expected: All six valid fixture order/customer pairs are returned.
-- Dialect: mysql, postgres

SELECT customer_id, tenant_id, order_id
FROM sqlt_customers
NATURAL JOIN sqlt_orders
ORDER BY order_id;
