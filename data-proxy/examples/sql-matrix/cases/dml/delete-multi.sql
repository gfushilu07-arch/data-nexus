-- case: SQLT-DML-025
-- Purpose: Verify a predicate DELETE removes every matching tenant row.
-- Expected: Both tenant 20 targets are absent and all tenant 10 targets remain.
-- Dialect: mysql, postgres

DELETE FROM sqlt_dml_targets
WHERE tenant_id = 20;
