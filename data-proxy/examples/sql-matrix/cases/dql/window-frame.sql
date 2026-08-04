-- case: SQLT-DQL-064
-- Purpose: Verify a ROWS window frame computes a running amount per tenant.
-- Expected: Running sums follow order_id order independently for tenants 10 and 20.
-- Dialect: mysql, postgres

SELECT order_id, tenant_id,
       SUM(total_amount) OVER (
           PARTITION BY tenant_id
           ORDER BY order_id
           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
       ) AS running_amount
FROM sqlt_orders
ORDER BY order_id;
