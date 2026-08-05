-- case: SQLT-DDL-003
-- Purpose: Verify that CREATE TABLE IF NOT EXISTS is idempotent for an existing table.
-- Expected: The statement succeeds without changing the existing table metadata.
-- Dialect: mysql, postgres

CREATE TABLE IF NOT EXISTS sqlt_ddl_if_not_exists (
    probe_id INTEGER NOT NULL PRIMARY KEY,
    probe_name VARCHAR(64) NOT NULL
);
