-- case: SQLT-DQL-039
-- Purpose: Verify multiple CTEs can be joined through a shared tenant key.
-- Expected: Each tenant row contains its customer count and exact order amount total.
-- Dialect: mysql, postgres

WITH customer_counts AS (
    SELECT tenant_id, COUNT(*) AS customer_count
    FROM sqlt_customers
    GROUP BY tenant_id
),
order_totals AS (
    SELECT tenant_id, SUM(total_amount) AS amount_sum
    FROM sqlt_orders
    GROUP BY tenant_id
)
SELECT c.tenant_id, c.customer_count, o.amount_sum
FROM customer_counts AS c
JOIN order_totals AS o ON o.tenant_id = c.tenant_id
ORDER BY c.tenant_id;
