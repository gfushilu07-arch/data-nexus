-- case: SQLT-DML-028
-- Purpose: Verify the MySQL JOIN DELETE dialect removes targets through customer tenant matching.
-- Expected: Both tenant 20 targets are absent and all tenant 10 targets remain.
-- Dialect: mysql

DELETE t
FROM sqlt_dml_targets AS t
JOIN sqlt_customers AS c ON c.customer_id = t.customer_id
WHERE c.tenant_id = 20;
