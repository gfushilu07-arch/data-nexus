-- case: SQLT-DML-029
-- Purpose: Verify the PostgreSQL DELETE USING dialect removes targets through customer tenant matching.
-- Expected: Both tenant 20 targets are absent and all tenant 10 targets remain.
-- Dialect: postgres

DELETE FROM sqlt_dml_targets AS t
USING sqlt_customers AS c
WHERE c.customer_id = t.customer_id AND c.tenant_id = 20;
