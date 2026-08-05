-- case: SQLT-DDL-033
-- Purpose: Create a named unique index with a deterministic composite column order.
-- Expected: sqlt_idx_probe indexes probe_name then probe_id and is unique.
-- Dialect: mysql, postgres

CREATE UNIQUE INDEX sqlt_idx_probe
ON sqlt_ddl_index (probe_name, probe_id);
