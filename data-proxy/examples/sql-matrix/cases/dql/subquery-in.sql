-- case: SQLT-DQL-035
-- Purpose: Verify IN consumes a subquery result set of customer identifiers.
-- Expected: The three orders owned by tenant 10 customers are returned.
-- Dialect: mysql, postgres

SELECT order_id
FROM sqlt_orders
WHERE customer_id IN (
    SELECT customer_id
    FROM sqlt_customers
    WHERE tenant_id = 10
)
ORDER BY order_id;
