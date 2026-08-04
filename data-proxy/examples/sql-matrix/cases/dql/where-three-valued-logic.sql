-- case: SQLT-DQL-013
-- Purpose: Verify explicit NULL handling across SQL three-valued predicate evaluation.
-- Expected: The NULL email row and non-Ada email rows are returned without losing UNKNOWN values.
-- Dialect: mysql, postgres

SELECT customer_id, email
FROM sqlt_customers
WHERE email IS NULL OR email <> 'ada@example.test'
ORDER BY customer_id;
