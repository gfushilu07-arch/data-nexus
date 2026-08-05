-- case: SQLT-DQL-067
-- Purpose: Verify PostgreSQL NULLS LAST places null sort keys after descending values.
-- Expected: Non-null emails descend deterministically and the null email is last.
-- Dialect: postgres

SELECT customer_id, email
FROM sqlt_customers
ORDER BY email DESC NULLS LAST, customer_id;
