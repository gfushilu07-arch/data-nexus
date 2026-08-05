-- fixture: SQLT-FIXTURE-MYSQL-DDL-CONSTRAINT-WITH-PK
-- Purpose: Create the MySQL baseline table with a primary key.
-- Expected: MySQL exposes the probe_id primary key with its canonical PRIMARY name.
-- Dialect: mysql

CREATE TABLE sqlt_ddl_constraint (
    probe_id INTEGER NOT NULL,
    probe_name VARCHAR(32) NOT NULL,
    CONSTRAINT sqlt_pk_probe PRIMARY KEY (probe_id)
);
