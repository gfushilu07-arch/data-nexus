-- case: SQLT-DQL-017
-- Purpose: Verify SUM, AVG, MIN, and MAX over exact decimal values.
-- Expected: One deterministic summary row is returned for all six fixture orders.
-- Dialect: mysql, postgres

SELECT SUM(total_amount) AS amount_sum,
       AVG(total_amount) AS amount_average,
       MIN(total_amount) AS amount_minimum,
       MAX(total_amount) AS amount_maximum
FROM sqlt_orders;
