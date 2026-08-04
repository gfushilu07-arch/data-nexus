-- case: SQLT-DQL-020
-- Purpose: Verify aggregate semantics when the input relation is empty.
-- Expected: One row is returned with row_count zero and amount_sum NULL.
-- Dialect: mysql, postgres

SELECT COUNT(*) AS row_count, SUM(total_amount) AS amount_sum
FROM sqlt_orders
WHERE order_id < 0;
