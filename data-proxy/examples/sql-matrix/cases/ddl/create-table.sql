-- case: SQLT-DDL-002
-- Purpose: Create a portable table with deterministic column metadata.
-- Expected: The table exists with the exact primary key and varchar columns.
-- Dialect: mysql, postgres

CREATE TABLE sqlt_ddl_create (
    probe_id INTEGER NOT NULL PRIMARY KEY,
    probe_name VARCHAR(64) NOT NULL
);
