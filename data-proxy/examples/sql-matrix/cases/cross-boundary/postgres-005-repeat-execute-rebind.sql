-- case: SQLT-XBND-005
-- Purpose: Verify the same PostgreSQL named statement re-Binds and executes with new parameters.
-- Expected: Three executes after re-Bind return tenant 10, tenant 20, then tenant 10 rows.
-- Dialect: postgres

-- @step select
SELECT display_name FROM sqlt_customers WHERE tenant_id = $1 ORDER BY customer_id;
