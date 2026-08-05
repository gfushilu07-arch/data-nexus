-- fixture: SQLT-FIXTURE-POSTGRES-DDL-CONSTRAINT-CHECK
-- Purpose: Create an empty PostgreSQL table without a check constraint.
-- Expected: probe_value can accept the positive-value check under test.
-- Dialect: postgres

CREATE TABLE sqlt_ddl_constraint (
    probe_id INTEGER NOT NULL,
    probe_value INTEGER NOT NULL
);
