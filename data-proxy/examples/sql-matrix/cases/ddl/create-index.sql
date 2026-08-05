-- case: SQLT-DDL-032
-- Purpose: Create a named non-unique index with a deterministic composite column order.
-- Expected: sqlt_idx_probe indexes probe_name then probe_id and remains non-unique.
-- Dialect: mysql, postgres

CREATE INDEX sqlt_idx_probe
ON sqlt_ddl_index (probe_name, probe_id);
