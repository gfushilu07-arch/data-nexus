-- case: SQLT-GOV-001
-- Purpose: Verify customer reads under each governance policy on a MySQL backend.
-- Expected: Baseline returns four ordered rows; the tenant filter policy returns only tenant 10.
-- Dialect: mysql

-- @step select
SELECT customer_id, display_name FROM sqlt_customers ORDER BY customer_id;
