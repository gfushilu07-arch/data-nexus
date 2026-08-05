-- fixture: SQLT-FIXTURE-MYSQL-DDL-ALTER-WITH-NOTE
-- Purpose: Create the reusable MySQL three-column baseline for DROP COLUMN.
-- Expected: sqlt_ddl_alter includes a nullable varchar(32) note as its final column.
-- Dialect: mysql

CREATE TABLE sqlt_ddl_alter (
    probe_id INTEGER NOT NULL PRIMARY KEY,
    probe_name VARCHAR(16) NOT NULL,
    probe_note VARCHAR(32)
);
