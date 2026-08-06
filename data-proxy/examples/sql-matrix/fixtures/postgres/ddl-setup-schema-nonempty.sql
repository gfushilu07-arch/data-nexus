-- fixture: SQLT-FIXTURE-POSTGRES-DDL-SCHEMA-NONEMPTY
-- Purpose: Create a PostgreSQL schema containing one deterministic probe table.
-- Expected: The schema owns sqlt_ddl_probe with two ordered columns.
-- Dialect: postgres

CREATE SCHEMA sqlt_ddl_schema;

CREATE TABLE sqlt_ddl_schema.sqlt_ddl_probe (
    probe_id INTEGER NOT NULL,
    probe_name VARCHAR(32) NOT NULL
);
