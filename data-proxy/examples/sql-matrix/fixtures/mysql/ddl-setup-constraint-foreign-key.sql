-- fixture: SQLT-FIXTURE-MYSQL-DDL-CONSTRAINT-FOREIGN-KEY
-- Purpose: Create matching MySQL parent and child rows without a foreign key.
-- Expected: parent_id can accept the named foreign key under test.
-- Dialect: mysql

CREATE TABLE sqlt_ddl_parent (
    parent_id INTEGER NOT NULL PRIMARY KEY
);

CREATE TABLE sqlt_ddl_constraint (
    probe_id INTEGER NOT NULL,
    parent_id INTEGER NOT NULL
);

INSERT INTO sqlt_ddl_parent (parent_id) VALUES (10);
INSERT INTO sqlt_ddl_constraint (probe_id, parent_id) VALUES (1, 10);
