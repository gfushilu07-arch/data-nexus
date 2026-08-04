-- case: SQLT-DQL-036
-- Purpose: Verify a grouped derived table can be filtered and ordered by an outer query.
-- Expected: Customers 101, 201, and 202 have aggregate order amounts above 40.00.
-- Dialect: mysql, postgres

SELECT totals.customer_id, totals.amount_sum
FROM (
    SELECT customer_id, SUM(total_amount) AS amount_sum
    FROM sqlt_orders
    GROUP BY customer_id
) AS totals
WHERE totals.amount_sum > 40.00
ORDER BY totals.customer_id;
