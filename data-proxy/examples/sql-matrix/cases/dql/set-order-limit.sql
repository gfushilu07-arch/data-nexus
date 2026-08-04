-- case: SQLT-DQL-045
-- Purpose: Verify ORDER BY and LIMIT apply to the complete UNION result.
-- Expected: The first four sorted distinct customer names and order statuses are returned.
-- Dialect: mysql, postgres

SELECT display_name AS value FROM sqlt_customers
UNION
SELECT status AS value FROM sqlt_orders
ORDER BY value
LIMIT 4;
