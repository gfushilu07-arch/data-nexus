-- case: SQLT-DQL-068
-- Purpose: Verify a MySQL boolean sort key provides deterministic NULLS FIRST semantics.
-- Expected: The null email is first, followed by ascending email and primary key.
-- Dialect: mysql

SELECT customer_id, email
FROM sqlt_customers
ORDER BY email IS NOT NULL, email, customer_id;
