-- oracle: SQLT-ORACLE-POSTGRES-READ-V1
-- Purpose: Produce a deterministic snapshot for direct-versus-gateway comparison.
-- Expected: Ordered customer and aggregate rows match MySQL semantic fixtures.
-- Dialect: postgres

SELECT customer_id, tenant_id, COALESCE(email, '<NULL>'), display_name
FROM sqlt_customers
ORDER BY customer_id;

SELECT c.tenant_id, c.customer_id, COUNT(o.order_id), SUM(o.total_amount)
FROM sqlt_customers AS c
JOIN sqlt_orders AS o ON o.customer_id = c.customer_id
GROUP BY c.tenant_id, c.customer_id
ORDER BY c.tenant_id, c.customer_id;
