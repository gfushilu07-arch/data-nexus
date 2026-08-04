-- case: SQLT-DQL-001
-- Purpose: Verify joins, aggregates, grouping, HAVING, and deterministic ordering.
-- Expected: The direct-backend oracle matches, with tenant rows filtered when required.
-- Dialect: mysql, postgres

SELECT c.tenant_id, c.customer_id, COUNT(o.order_id) AS order_count,
       SUM(o.total_amount) AS total_amount
FROM sqlt_customers AS c
JOIN sqlt_orders AS o ON o.customer_id = c.customer_id
GROUP BY c.tenant_id, c.customer_id
HAVING COUNT(o.order_id) >= 1
ORDER BY c.tenant_id, c.customer_id;
