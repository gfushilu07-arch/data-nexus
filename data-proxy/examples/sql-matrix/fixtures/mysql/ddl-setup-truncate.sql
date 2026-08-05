-- fixture: SQLT-FIXTURE-MYSQL-DDL-TRUNCATE
-- Purpose: Create and seed the MySQL table used by the TRUNCATE case.
-- Expected: sqlt_ddl_truncate contains exactly three rows before execution.
-- Dialect: mysql

CREATE TABLE sqlt_ddl_truncate (
    probe_id INTEGER NOT NULL PRIMARY KEY,
    probe_name VARCHAR(16) NOT NULL
);
INSERT INTO sqlt_ddl_truncate (probe_id, probe_name)
VALUES (1, 'one'), (2, 'two'), (3, 'three');
