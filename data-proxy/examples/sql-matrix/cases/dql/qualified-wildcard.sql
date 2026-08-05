-- case: SQLT-DQL-069
-- Purpose: Verify a qualified wildcard projects only the named relation in schema order.
-- Expected: Every customer column is returned in primary-key order.
-- Dialect: mysql, postgres

SELECT customer.*
FROM sqlt_customers AS customer
ORDER BY customer.customer_id;
