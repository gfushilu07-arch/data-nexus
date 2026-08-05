-- fixture: SQLT-FIXTURE-MYSQL-DDL-INDEX-EXISTING
-- Purpose: Create a MySQL table with an existing named composite index.
-- Expected: sqlt_idx_probe indexes probe_name then probe_id and is non-unique.
-- Dialect: mysql

CREATE TABLE sqlt_ddl_index (
    probe_id INTEGER NOT NULL,
    probe_name VARCHAR(32) NOT NULL
);

CREATE INDEX sqlt_idx_probe
ON sqlt_ddl_index (probe_name, probe_id);
