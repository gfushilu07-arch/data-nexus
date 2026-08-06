-- case: SQLT-PGX-004
-- Purpose: Execute two named portals bound independently to one prepared statement.
-- Expected: Interleaved portal execution preserves each tenant binding and result set.
-- Dialect: postgres

SELECT customer_id, display_name
FROM sqlt_customers
WHERE tenant_id = $1
ORDER BY customer_id;
