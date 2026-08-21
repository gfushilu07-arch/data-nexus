-- case: SQLT-XBND-005
-- Purpose: Verify the same MySQL prepared statement executes repeatedly with rebound parameters.
-- Expected: Three executes on one statement return tenant 10, tenant 20, then tenant 10 rows.
-- Dialect: mysql

-- @step select
SELECT display_name FROM sqlt_customers WHERE tenant_id = ? ORDER BY customer_id;
