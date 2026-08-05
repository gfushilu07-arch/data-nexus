-- case: SQLT-DDL-036
-- Purpose: Attempt to create an index whose name already exists.
-- Expected: Execution fails with a stable duplicate-name error and preserves the original index.
-- Dialect: mysql, postgres

CREATE INDEX sqlt_idx_probe
ON sqlt_ddl_index (probe_id);
