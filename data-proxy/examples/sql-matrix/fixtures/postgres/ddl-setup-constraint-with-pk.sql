-- fixture: SQLT-FIXTURE-POSTGRES-DDL-CONSTRAINT-WITH-PK
-- Purpose: Create the PostgreSQL baseline table with a named primary key.
-- Expected: PostgreSQL exposes sqlt_pk_probe on probe_id.
-- Dialect: postgres

CREATE TABLE sqlt_ddl_constraint (
    probe_id INTEGER NOT NULL,
    probe_name VARCHAR(32) NOT NULL,
    CONSTRAINT sqlt_pk_probe PRIMARY KEY (probe_id)
);
