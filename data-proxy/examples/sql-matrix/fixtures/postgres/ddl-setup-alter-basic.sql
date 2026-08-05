-- fixture: SQLT-FIXTURE-POSTGRES-DDL-ALTER-BASIC
-- Purpose: Create the reusable PostgreSQL two-column baseline for ALTER TABLE cases.
-- Expected: sqlt_ddl_alter has an integer key and a not-null varchar(16) name.
-- Dialect: postgres

CREATE TABLE sqlt_ddl_alter (
    probe_id INTEGER NOT NULL PRIMARY KEY,
    probe_name VARCHAR(16) NOT NULL
);
