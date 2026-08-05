-- fixture: SQLT-FIXTURE-MYSQL-DDL-CONSTRAINT-UNIQUE
-- Purpose: Create a MySQL table with distinct values and no unique constraint.
-- Expected: probe_name can accept the named unique constraint under test.
-- Dialect: mysql

CREATE TABLE sqlt_ddl_constraint (
    probe_id INTEGER NOT NULL,
    probe_name VARCHAR(32) NOT NULL
);

INSERT INTO sqlt_ddl_constraint (probe_id, probe_name)
VALUES (1, 'alpha'), (2, 'beta');
