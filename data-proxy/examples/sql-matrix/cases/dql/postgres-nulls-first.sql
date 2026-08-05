-- case: SQLT-DQL-066
-- Purpose: Verify PostgreSQL NULLS FIRST places null sort keys before non-null values.
-- Expected: The null email is first, followed by ascending email and primary key.
-- Dialect: postgres

SELECT customer_id, email
FROM sqlt_customers
ORDER BY email ASC NULLS FIRST, customer_id;
