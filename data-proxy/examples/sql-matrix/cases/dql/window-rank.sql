-- case: SQLT-DQL-047
-- Purpose: Verify RANK and DENSE_RANK differ when the ordering key contains ties.
-- Expected: Tenant 20 starts at rank 4 but dense rank 2 after three tenant 10 rows.
-- Dialect: mysql, postgres

SELECT order_id, tenant_id,
       RANK() OVER (ORDER BY tenant_id) AS tenant_rank,
       DENSE_RANK() OVER (ORDER BY tenant_id) AS tenant_dense_rank
FROM sqlt_orders
ORDER BY order_id;
