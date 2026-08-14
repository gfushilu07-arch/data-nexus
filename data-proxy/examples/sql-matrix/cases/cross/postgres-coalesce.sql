-- case: SQLT-XDQL-002
-- Purpose: Verify PostgreSQL COALESCE remains valid through translation to a MySQL backend.
-- Expected: Nullable email values use the fixed fallback and rows remain ordered.
-- Dialect: postgres

SELECT customer_id,
       CASE WHEN email IS NULL THEN 'missing' ELSE 'present' END AS email_state,
       COALESCE(email, 'not-provided@example.test') AS normalized_email
FROM sqlt_customers
ORDER BY customer_id;
