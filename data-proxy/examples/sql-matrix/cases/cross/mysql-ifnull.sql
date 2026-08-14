-- case: SQLT-XDQL-002
-- Purpose: Verify MySQL IFNULL is rewritten to a PostgreSQL-compatible fallback expression.
-- Expected: Nullable email values use the fixed fallback and rows remain ordered.
-- Dialect: mysql

SELECT customer_id,
       CASE WHEN email IS NULL THEN 'missing' ELSE 'present' END AS email_state,
       IFNULL(email, 'not-provided@example.test') AS normalized_email
FROM sqlt_customers
ORDER BY customer_id;
