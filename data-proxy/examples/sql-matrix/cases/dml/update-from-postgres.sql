-- case: SQLT-DML-023
-- Purpose: Verify the PostgreSQL UPDATE FROM dialect updates targets from customer names.
-- Expected: Tenant 20 descriptions use Grace and Edsger display names and joined status.
-- Dialect: postgres

UPDATE sqlt_dml_targets AS t
SET description = c.display_name || '-joined', status = 'joined'
FROM sqlt_customers AS c
WHERE c.customer_id = t.customer_id AND c.tenant_id = 20;
