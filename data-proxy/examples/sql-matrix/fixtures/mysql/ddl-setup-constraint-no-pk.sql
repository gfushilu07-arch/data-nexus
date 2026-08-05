-- fixture: SQLT-FIXTURE-MYSQL-DDL-CONSTRAINT-NO-PK
-- Purpose: Create the MySQL baseline table without a primary key.
-- Expected: Both columns are not null and no table constraint is present.
-- Dialect: mysql

CREATE TABLE sqlt_ddl_constraint (
    probe_id INTEGER NOT NULL,
    probe_name VARCHAR(32) NOT NULL
);
