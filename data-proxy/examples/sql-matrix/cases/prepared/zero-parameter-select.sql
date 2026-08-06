-- case: SQLT-PRP-001
-- Purpose: Prepare, execute, describe, and close a zero-parameter SELECT.
-- Expected: Binary rows and column metadata remain identical through direct and gateway paths.
-- Dialect: mysql

SELECT customer_id, display_name
FROM sqlt_customers
ORDER BY customer_id
LIMIT 2
