-- case: SQLT-PGX-001
-- Purpose: Exercise a named statement and portal through the complete extended-query lifecycle.
-- Expected: Describe and Execute return deterministic customer metadata and rows before both objects close.
-- Dialect: postgres

SELECT customer_id, display_name
FROM sqlt_customers
WHERE tenant_id = $1
ORDER BY customer_id;
