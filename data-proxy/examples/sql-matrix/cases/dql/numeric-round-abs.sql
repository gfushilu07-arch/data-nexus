-- case: SQLT-DQL-052
-- Purpose: Verify absolute value and decimal rounding in a numeric projection.
-- Expected: Each order returns a positive amount rounded to one decimal place.
-- Dialect: mysql, postgres

SELECT order_id,
       ABS(total_amount - 50.00) AS distance_from_50,
       ROUND(total_amount, 1) AS rounded_amount
FROM sqlt_orders
ORDER BY order_id;
