-- fixture: SQLT-FIXTURE-MYSQL-DDL-INDEX-BASIC
-- Purpose: Create a MySQL table with distinct rows and no indexes.
-- Expected: sqlt_ddl_index is ready for ordinary or unique composite index creation.
-- Dialect: mysql

CREATE TABLE sqlt_ddl_index (
    probe_id INTEGER NOT NULL,
    probe_name VARCHAR(32) NOT NULL
);

INSERT INTO sqlt_ddl_index (probe_id, probe_name)
VALUES (1, 'alpha'), (2, 'beta');
