-- case: SQLT-DQL-058
-- Purpose: Verify month-level timestamp truncation for grouped reporting keys.
-- Expected: The six timestamps normalize to January and February 2026 month starts.
-- Dialect: postgres

SELECT order_id,
       DATE_TRUNC('month', created_at) AS month_start
FROM sqlt_orders
ORDER BY order_id;
