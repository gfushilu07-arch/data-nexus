-- case: SQLT-DQL-062
-- Purpose: Verify PostgreSQL regular-expression matching against fixture emails.
-- Expected: Ada and Grace are returned because their email local parts begin with a.
-- Dialect: postgres

SELECT customer_id, email
FROM sqlt_customers
WHERE email ~ '^[ag].*@example\.test$'
ORDER BY customer_id;
