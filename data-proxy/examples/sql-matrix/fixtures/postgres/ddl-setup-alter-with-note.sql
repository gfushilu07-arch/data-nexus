-- fixture: SQLT-FIXTURE-POSTGRES-DDL-ALTER-WITH-NOTE
-- Purpose: Create the reusable PostgreSQL three-column baseline for DROP COLUMN.
-- Expected: sqlt_ddl_alter includes a nullable varchar(32) note as its final column.
-- Dialect: postgres

CREATE TABLE sqlt_ddl_alter (
    probe_id INTEGER NOT NULL PRIMARY KEY,
    probe_name VARCHAR(16) NOT NULL,
    probe_note VARCHAR(32)
);
