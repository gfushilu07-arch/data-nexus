-- case: SQLT-DQL-080
-- Purpose: Verify a half-open timestamp range includes exact lower and excludes upper boundaries.
-- Expected: Orders from January 2 through February 1 are returned chronologically.
-- Dialect: mysql, postgres

SELECT order_id, customer_id, total_amount
FROM sqlt_orders
WHERE created_at >= '2026-01-02 00:00:00'
  AND created_at < '2026-02-02 00:00:00'
ORDER BY created_at, order_id;
