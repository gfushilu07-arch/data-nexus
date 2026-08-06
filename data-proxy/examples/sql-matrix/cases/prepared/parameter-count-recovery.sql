-- case: SQLT-PRP-006
-- Purpose: Observe missing and extra prepared bindings, then recover on the same cursor.
-- Expected: Missing binds yield no row, extra binds fail, and a valid execute returns one row.
-- Dialect: mysql

SELECT customer_id
FROM sqlt_customers
WHERE customer_id = %s
