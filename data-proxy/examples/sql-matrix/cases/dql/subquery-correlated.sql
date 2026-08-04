-- case: SQLT-DQL-034
-- Purpose: Verify a correlated scalar subquery evaluates once per outer customer row.
-- Expected: Per-customer order counts are returned as 2, 1, 2, and 1.
-- Dialect: mysql, postgres

SELECT c.customer_id,
       (
           SELECT COUNT(*)
           FROM sqlt_orders AS o
           WHERE o.customer_id = c.customer_id
       ) AS order_count
FROM sqlt_customers AS c
ORDER BY c.customer_id;
