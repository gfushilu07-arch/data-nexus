-- fixture: SQLT-FIXTURE-POSTGRES-DDL-UNIQUE-CONFLICT
-- Purpose: Create a PostgreSQL table containing duplicate values and no unique constraint.
-- Expected: Adding a unique constraint over probe_value is rejected.
-- Dialect: postgres

CREATE TABLE sqlt_ddl_constraint (
    probe_id INTEGER NOT NULL,
    probe_value INTEGER NOT NULL
);

INSERT INTO sqlt_ddl_constraint (probe_id, probe_value)
VALUES (1, 5), (2, 5);
