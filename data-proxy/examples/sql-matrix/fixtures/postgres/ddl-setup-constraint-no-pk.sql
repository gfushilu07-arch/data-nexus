-- fixture: SQLT-FIXTURE-POSTGRES-DDL-CONSTRAINT-NO-PK
-- Purpose: Create the PostgreSQL baseline table without a primary key.
-- Expected: Both columns are not null and no table constraint is present.
-- Dialect: postgres

CREATE TABLE sqlt_ddl_constraint (
    probe_id INTEGER NOT NULL,
    probe_name VARCHAR(32) NOT NULL
);
