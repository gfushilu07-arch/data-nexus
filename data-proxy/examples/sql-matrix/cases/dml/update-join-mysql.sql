-- case: SQLT-DML-022
-- Purpose: Verify the MySQL JOIN UPDATE dialect updates targets from customer names.
-- Expected: Tenant 20 descriptions use Grace and Edsger display names and joined status.
-- Dialect: mysql

UPDATE sqlt_dml_targets AS t
JOIN sqlt_customers AS c ON c.customer_id = t.customer_id
SET t.description = CONCAT(c.display_name, '-joined'), t.status = 'joined'
WHERE c.tenant_id = 20;
