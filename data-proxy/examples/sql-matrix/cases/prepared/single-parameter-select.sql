-- case: SQLT-PRP-002
-- Purpose: Bind one integer parameter to a prepared predicate.
-- Expected: The matching customer row is returned with stable binary column metadata.
-- Dialect: mysql

SELECT customer_id, display_name
FROM sqlt_customers
WHERE customer_id = %s
