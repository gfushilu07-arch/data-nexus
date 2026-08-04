-- case: SQLT-DQL-003
-- Purpose: Verify wildcard handling at the column-authorization boundary.
-- Expected: Allow returns all columns; deny and fail-closed column stripping reject it.
-- Dialect: mysql, postgres

SELECT *
FROM sqlt_customers
ORDER BY customer_id;
