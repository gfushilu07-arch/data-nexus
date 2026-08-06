-- fixture: SQLT-FIXTURE-MYSQL-PREPARED-SCHEMA-SETUP
-- Purpose: Create the table used to observe prepared statement schema invalidation.
-- Expected: One single-column row exists before the prepared wildcard query runs.
-- Dialect: mysql

CREATE TABLE sqlt_prepared_schema (
    probe_id INTEGER NOT NULL PRIMARY KEY
) ENGINE = InnoDB;
INSERT INTO sqlt_prepared_schema (probe_id) VALUES (1);
