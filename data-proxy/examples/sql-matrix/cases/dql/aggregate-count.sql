-- case: SQLT-DQL-016
-- Purpose: Verify COUNT(*) over all rows in a fixture relation.
-- Expected: One row is returned with order_count equal to 6.
-- Dialect: mysql, postgres

SELECT COUNT(*) AS order_count
FROM sqlt_orders;
