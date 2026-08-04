-- case: SQLT-DQL-038
-- Purpose: Verify a non-recursive CTE can be grouped by the consuming query.
-- Expected: Paid order counts and sums are returned for tenants 10 and 20.
-- Dialect: mysql, postgres

WITH paid_orders AS (
    SELECT tenant_id, total_amount
    FROM sqlt_orders
    WHERE status = 'paid'
)
SELECT tenant_id, COUNT(*) AS paid_count, SUM(total_amount) AS paid_sum
FROM paid_orders
GROUP BY tenant_id
ORDER BY tenant_id;
