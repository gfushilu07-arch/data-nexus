-- case: SQLT-DQL-054
-- Purpose: Verify CASE classification and COALESCE fallback for nullable email values.
-- Expected: Customer 102 receives the `missing` classification and fallback email.
-- Dialect: mysql, postgres

SELECT customer_id,
       CASE WHEN email IS NULL THEN 'missing' ELSE 'present' END AS email_state,
       COALESCE(email, 'not-provided@example.test') AS normalized_email
FROM sqlt_customers
ORDER BY customer_id;
