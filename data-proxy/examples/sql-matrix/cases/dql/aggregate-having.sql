-- case: SQLT-DQL-019
-- Purpose: Verify HAVING filters grouped aggregate results after grouping.
-- Expected: Only tenants whose total order amount exceeds 100.00 are returned.
-- Dialect: mysql, postgres

SELECT tenant_id, SUM(total_amount) AS amount_sum
FROM sqlt_orders
GROUP BY tenant_id
HAVING SUM(total_amount) > 100.00
ORDER BY tenant_id;
