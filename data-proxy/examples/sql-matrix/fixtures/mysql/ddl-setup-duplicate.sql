-- fixture: SQLT-FIXTURE-MYSQL-DDL-DUPLICATE
-- Purpose: Create the MySQL baseline table used by the duplicate CREATE error case.
-- Expected: The baseline table exists before the tested CREATE statement runs.
-- Dialect: mysql

CREATE TABLE sqlt_ddl_duplicate (
    probe_id INTEGER NOT NULL PRIMARY KEY,
    probe_name VARCHAR(64) NOT NULL
);
