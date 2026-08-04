-- case: SQLT-DQL-063
-- Purpose: Verify MySQL REGEXP_LIKE matching against fixture emails.
-- Expected: Ada and Grace are returned because their email local parts begin with a.
-- Dialect: mysql

SELECT customer_id, email
FROM sqlt_customers
WHERE REGEXP_LIKE(email, '^[ag].*@example\\.test$')
ORDER BY customer_id;
