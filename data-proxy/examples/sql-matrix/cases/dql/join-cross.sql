-- case: SQLT-DQL-029
-- Purpose: Verify CROSS JOIN produces the Cartesian product of two bounded inputs.
-- Expected: Two selected customers are paired with each of the three distinct statuses.
-- Dialect: mysql, postgres

SELECT c.customer_id, s.status
FROM (
    SELECT customer_id
    FROM sqlt_customers
    WHERE customer_id IN (101, 202)
) AS c
CROSS JOIN (
    SELECT DISTINCT status
    FROM sqlt_orders
) AS s
ORDER BY c.customer_id, s.status;
