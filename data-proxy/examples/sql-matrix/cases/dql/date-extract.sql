-- case: SQLT-DQL-057
-- Purpose: Verify date extraction from deterministic timestamp columns.
-- Expected: Each order returns its calendar year and month in order_id order.
-- Dialect: mysql, postgres

SELECT order_id,
       EXTRACT(YEAR FROM created_at) AS created_year,
       EXTRACT(MONTH FROM created_at) AS created_month
FROM sqlt_orders
ORDER BY order_id;
