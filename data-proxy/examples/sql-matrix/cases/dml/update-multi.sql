-- case: SQLT-DML-016
-- Purpose: Verify a predicate UPDATE changes every matching tenant row exactly once.
-- Expected: All three tenant 10 targets have status tenant-updated; two tenant 20 rows remain ready or archived.
-- Dialect: mysql, postgres

UPDATE sqlt_dml_targets
SET status = 'tenant-updated'
WHERE tenant_id = 10;
