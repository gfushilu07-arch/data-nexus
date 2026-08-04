-- case: SQLT-INVALID-001
-- Purpose: Verify malformed SQL is rejected consistently before backend side effects.
-- Expected: Every policy path returns a syntax or policy denial and no rows.
-- Dialect: mysql, postgres

SELECT customer_id, FROM sqlt_customers;
