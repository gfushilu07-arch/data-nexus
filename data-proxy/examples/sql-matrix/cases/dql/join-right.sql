-- case: SQLT-DQL-027
-- Purpose: Verify RIGHT JOIN preserves every row from the order relation.
-- Expected: All six orders are returned with their matching customer IDs.
-- Dialect: mysql, postgres

SELECT c.customer_id, o.order_id
FROM sqlt_customers AS c
RIGHT JOIN sqlt_orders AS o ON o.customer_id = c.customer_id
ORDER BY o.order_id;
