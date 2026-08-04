-- case: SQLT-DQL-033
-- Purpose: Verify an uncorrelated scalar aggregate subquery in the projection list.
-- Expected: Every customer row includes the global maximum order amount of 120.00.
-- Dialect: mysql, postgres

SELECT c.customer_id,
       (SELECT MAX(o.total_amount) FROM sqlt_orders AS o) AS maximum_amount
FROM sqlt_customers AS c
ORDER BY c.customer_id;
